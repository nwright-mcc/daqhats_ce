#!/usr/bin/env python3
"""
    MCC 134 CE Test application

    Purpose:
        Exercise the MCC 134 for emissions / immunity testing

    Description:
        This app reads and displays the input voltages.
"""
from daqhats import mcc134, TcTypes
from tkinter import *
import datetime
from tkinter import messagebox
import os
#import tkinter.font

DEFAULT_TC_LIMIT = 20.0    # uV
DEFAULT_CJC_LIMIT = 2.0    # C

class LED(Frame):
    def __init__(self, parent, size=10, **options):
        self.size = size
        Frame.__init__(self, parent, width=size+1, height=size+1)
        self.configure(**options)
        self.state = 0
        self.c = Canvas(self, width=self['width'], height=self['height'])
        self.c.grid()
        self.led = self._drawcircle((self.size/2)+1, (self.size/2)+1,
            (self.size-1)/2)
        
    def _drawcircle(self, x, y, rad):
        color="gray"
        return self.c.create_oval(x-rad, y-rad, x+rad, y+rad, width=rad/5,
            fill=color, outline="dim gray")
            
    def _change_color(self):
        if self.state == 1:
            color = "lawn green"
        elif self.state == 2:
            color = "red"
        else:
            color = "gray"
        self.c.itemconfig(self.led, fill=color)
    
    def set(self, state):
        self.state = state
        self._change_color()
        
    def get(self):
        return self.state
    
class ControlApp:
    
    def __init__(self, master):
        self.master = master
        master.title("MCC 134 CE Test")
    
        # Initialize variables
        self.device_open = False
        self.board = None
        self.tc_limit = DEFAULT_TC_LIMIT
        self.cjc_limit = DEFAULT_CJC_LIMIT
        self.tc_voltages = [0.0]*mcc134.info().NUM_AI_CHANNELS
        self.tc_failures = [0]*mcc134.info().NUM_AI_CHANNELS
        self.cjc_temps = [0.0]*mcc134.info().NUM_AI_CHANNELS
        self.cjc_errors = [0.0]*mcc134.info().NUM_AI_CHANNELS
        self.baseline_temps = [0.0]*mcc134.info().NUM_AI_CHANNELS
        self.cjc_failures = [0]*mcc134.info().NUM_AI_CHANNELS
        self.test_count = 0
        self.software_errors = 0
        self.baseline_set = False
        self.watchdog_count = 0
        self.csvfile = None

        # GUI Setup

        # Device Frame
        self.device_frame = LabelFrame(master, text="Device status")
        #self.device_frame.pack(side=TOP, expand=False, fill=X)
        self.device_frame.grid(row=0, column=0, padx=3, pady=3,
                               sticky="NSEW")
        
        # Device widgets
        label = Label(self.device_frame, text="Serial number:")
        label.grid(row=0, column=0, padx=3, pady=3, sticky="E")
        self.serial_number = StringVar(self.device_frame, "00000000")
        label = Label(self.device_frame, width=8, textvariable=self.serial_number,
                      relief=SUNKEN)
        label.grid(row=0, column=1, padx=3, pady=3, ipadx=2, ipady=2)
        
        label = Label(self.device_frame, text="Software errors:")
        label.grid(row=1, column=0, padx=3, pady=3, sticky="E")
        self.software_error_label = Label(
            self.device_frame, width=8, text="0", relief=SUNKEN)
        self.software_error_label.grid(row=1, column=1, padx=3, pady=3,
                                       ipadx=2, ipady=2)

        label = Label(self.device_frame, text="Ready:")
        label.grid(row=0, column=3, padx=3, pady=3, sticky="E")
        self.ready_led = LED(self.device_frame, size=20)
        self.ready_led.grid(row=0, column=4, padx=3, pady=3)
        
        label = Label(self.device_frame, text="Activity:")
        label.grid(row=1, column=3, padx=3, pady=3, sticky="E")
        self.activity_led = LED(self.device_frame, size=20)
        self.activity_led.grid(row=1, column=4, padx=3, pady=3)
        
        # empty column for stretching
        self.device_frame.grid_columnconfigure(2, weight=1)
        
        
        # Test Frame
        self.test_frame = LabelFrame(master, text="Test status")
        self.test_frame.grid(row=0, column=1, columnspan=2,
                             sticky="NSEW", padx=3, pady=3)

        # Test widgets
        label = Label(self.test_frame, text="Pass/fail (latch):")
        label.grid(row=0, column=0, padx=3, pady=3, sticky="E")
        self.pass_led = LED(self.test_frame, size=20)
        self.pass_led.grid(row=0, column=1, padx=3, pady=3)

        label = Label(self.test_frame, text="Pass/fail (inst):")
        label.grid(row=1, column=0, padx=3, pady=3, sticky="E")
        self.inst_pass_led = LED(self.test_frame, size=20)
        self.inst_pass_led.grid(row=1, column=1, padx=3, pady=3)

        label = Label(self.test_frame, text="Test count:")
        label.grid(row=0, column=2, padx=3, pady=3, sticky="E")
        self.test_count_label = Label(self.test_frame, width=8,
                                      text="0", relief=SUNKEN)
        self.test_count_label.grid(row=0, column=3, padx=3, pady=3)
        
        self.stop_button = Button(self.test_frame, text="Stop", fg="red",
                                  command=self.stopTest)
        self.stop_button.grid(row=0, column=4, padx=3, pady=3, sticky="NSEW")
        self.reset_button = Button(self.test_frame, text="Reset",
                                   command=self.resetTest)
        self.reset_button.grid(row=1, column=4, padx=3, pady=3, sticky="NSEW")
        
        v = IntVar()
        self.watchdog_check = Checkbutton(
            self.test_frame, text="Use watchdog", variable=v)
        self.watchdog_check.var = v
        self.watchdog_check.grid(row=1, column=2, columnspan=2, padx=3, pady=3,
                                 sticky="W")

        # TC Frame
        self.tc_frame = LabelFrame(master, text="Thermocouple Inputs")
        #self.tc_frame.pack(side=BOTTOM, expand=True, fill=BOTH)
        self.tc_frame.grid(row=1, column=0, sticky="NSEW", padx=3, pady=3)

        # TC widgets
        label = Label(self.tc_frame, text="Limit: ±")
        label.grid(row=0, column=0, padx=3, pady=3, sticky="E")
        label = Label(self.tc_frame, text="{:.1f}".format(self.tc_limit),
                      relief=SUNKEN, anchor=E, width=8)
        label.grid(row=0, column=1, padx=3, pady=3, ipadx=2, ipady=2)
        
        label = Label(self.tc_frame, text="Channel")
        label.grid(row=1, column=0, padx=3, pady=3)
        label = Label(self.tc_frame, text="Current")
        label.grid(row=1, column=1, padx=3, pady=3)
        label = Label(self.tc_frame, text="Failures")
        label.grid(row=1, column=2, padx=3, pady=3)
        
        self.tc_voltage_labels = []
        self.tc_failure_labels = []
        
        for index in range(mcc134.info().NUM_AI_CHANNELS):
            # Labels
            label = Label(self.tc_frame, text="{}".format(index))
            label.grid(row=index+2, column=0, padx=3, pady=3)
            #label.grid_configure(sticky="W")
            
            # TC Voltages
            self.tc_voltage_labels.append(Label(self.tc_frame, width=8, anchor=E,
                                                text="0.0", relief=SUNKEN))
            self.tc_voltage_labels[index].grid(row=index+2, column=1, padx=3,
                                               pady=3, ipadx=2, ipady=2)
            self.tc_voltage_labels[index].grid_configure(sticky="E")

            self.tc_failure_labels.append(Label(self.tc_frame, width=8, anchor=E,
                                                relief=SUNKEN, text="0"))
            self.tc_failure_labels[index].grid(row=index+2, column=2, padx=3,
                                               pady=3, ipadx=2, ipady=2)
            
            #self.tc_frame.grid_rowconfigure(index, weight=1)
            
        #self.tc_frame.grid_columnconfigure(1, weight=1)
        #self.tc_frame.grid_columnconfigure(2, weight=1)


        # CJC Frame
        self.cjc_frame = LabelFrame(master, text="CJC Sensors")
        #self.cjc_frame.pack(side=BOTTOM, expand=True, fill=BOTH)
        self.cjc_frame.grid(row=1, column=1, sticky="NSEW", padx=3, pady=3)
        
        # CJC widgets
        label = Label(self.cjc_frame, text="Limit: ±")
        label.grid(row=0, column=2, padx=3, pady=3, sticky="E")
        label = Label(self.cjc_frame, relief=SUNKEN, anchor=E, width=6,
                      text="{:.1f}".format(self.cjc_limit))
        label.grid(row=0, column=3, padx=3, pady=3, ipadx=2, ipady=2, sticky="NSEW")
        
        label = Label(self.cjc_frame, text="Channel")
        label.grid(row=1, column=0, padx=3, pady=3)
        label = Label(self.cjc_frame, text="Baseline")
        label.grid(row=1, column=1, padx=3, pady=3)
        label = Label(self.cjc_frame, text="Current")
        label.grid(row=1, column=2, padx=3, pady=3)
        label = Label(self.cjc_frame, text="Difference")
        label.grid(row=1, column=3, padx=3, pady=3)
        label = Label(self.cjc_frame, text="Failures")
        label.grid(row=1, column=4, padx=3, pady=3)

        self.baseline_temp_labels = []
        self.cjc_temp_labels = []
        self.cjc_error_labels = []
        self.cjc_failure_labels = []
        
        for index in range(mcc134.info().NUM_AI_CHANNELS):
            label = Label(self.cjc_frame, text="{}".format(index))
            label.grid(row=index+2, column=0, padx=3, pady=3)
            #label.grid_configure(sticky="W")
            
            self.baseline_temp_labels.append(Label(self.cjc_frame, width=6,
                                                   anchor=E, text="0.0",
                                                   relief=SUNKEN))
            self.baseline_temp_labels[index].grid(row=index+2, column=1, padx=3,
                                                  pady=3, ipadx=2, ipady=2, sticky="NSEW")
            #self.baseline_temp_labels[index].grid_configure(sticky="E")

            self.cjc_temp_labels.append(Label(self.cjc_frame, width=6, anchor=E,
                                              text="0.0", relief=SUNKEN))
            self.cjc_temp_labels[index].grid(row=index+2, column=2, padx=3, pady=3,
                                             ipadx=2, ipady=2, sticky="NSEW")
            #self.cjc_temp_labels[index].grid_configure(sticky="E")
            
            self.cjc_error_labels.append(Label(self.cjc_frame, width=6, anchor=E,
                                               text="0.0", relief=SUNKEN))
            self.cjc_error_labels[index].grid(row=index+2, column=3, padx=3, pady=3,
                                              ipadx=2, ipady=2, sticky="NSEW")
            #self.cjc_error_labels[index].grid_configure(sticky="E")
            
            self.cjc_failure_labels.append(Label(self.cjc_frame, width=8, anchor=E,
                                                 relief=SUNKEN, text="0"))
            self.cjc_failure_labels[index].grid(row=index+2, column=4, padx=3,
                                                pady=3, ipadx=2, ipady=2, sticky="NSEW")
            
        master.protocol('WM_DELETE_WINDOW', self.close) # exit cleanup

        icon = PhotoImage(file='/usr/share/mcc/daqhats/icon.png')
        master.tk.call('wm', 'iconphoto', master._w, icon)

        self.pass_led.set(1)

        self.master.after(500, self.establishBaseline)

    def initBoard(self):
        # Try to initialize the device
        try:
            self.board = mcc134(0)
            
            serial = self.board.serial()
            self.serial_number.set(serial)
            
            for channel in range(mcc134.info().NUM_AI_CHANNELS):
                self.board.tc_type_write(channel, TcTypes.TYPE_T)
                
            self.ready_led.set(1)
            self.device_open = True
        except:
            self.software_errors += 1
            self.current_failures += 1
   
    def stopTest(self):
        # Stop the test loop
        if self.id:
            self.master.after_cancel(self.id)
        if self.csvfile:
            self.csvfile.close()
            self.csvfile = None
    
    def resetTest(self):
        # Reset the error counters and restart
        if self.id:
            self.master.after_cancel(self.id)
        if self.activity_id:
            self.master.after_cancel(self.activity_id)
        if self.pass_id:
            self.master.after_cancel(self.pass_id)

        if self.csvfile:
            self.csvfile.close()
            self.csfvile = None
            
        self.board = None
        self.device_open = False
        self.tc_voltages = [0.0]*mcc134.info().NUM_AI_CHANNELS
        self.tc_failures = [0]*mcc134.info().NUM_AI_CHANNELS
        self.cjc_temps = [0.0]*mcc134.info().NUM_AI_CHANNELS
        self.cjc_errors = [0.0]*mcc134.info().NUM_AI_CHANNELS
        self.baseline_temps = [0.0]*mcc134.info().NUM_AI_CHANNELS
        self.cjc_failures = [0]*mcc134.info().NUM_AI_CHANNELS
        self.test_count = 0
        self.software_errors = 0
        self.baseline_set = False
        self.watchdog_count = 0
        self.pass_led.set(1)
        self.inst_pass_led.set(0)

        self.ready_led.set(0)
        self.master.after(500, self.establishBaseline)
    
    def establishBaseline(self):
        self.id = None
        self.current_failures = 0
        
        if self.device_open:
            self.activity_led.set(1)
            self.activity_id = self.master.after(100, self.activityBlink)
            
            self.current_failures = 0
            try:
                for channel in range(mcc134.info().NUM_AI_CHANNELS):
                    # read the cjc value
                    self.cjc_temps[channel] = self.board.cjc_read(channel)
                    self.baseline_temps[channel] = self.cjc_temps[channel]
                self.baseline_set = True
                self.watchdog_count = 0
                
                # Create csv file with current date/time in file name
                self.openCsvFile()

                # go to the test loop
                self.id = self.master.after(1000, self.updateInputs)
            except FileNotFoundError:
                messagebox.showerror("Error", "Cannot create CSV file")
            except:
                self.software_errors += 1
                self.current_failures += 1
                self.watchdog_count += 1
                
                # try again
                self.id = self.master.after(1000, self.establishBaseline)
                
            self.updateDisplay()
        else:
            # Open the device
            self.initBoard()
            # schedule another attempt
            self.id = self.master.after(500, self.establishBaseline)
        
    def openCsvFile(self):
        if not os.path.isdir('./data'):
            # create the data directory
            os.mkdir('./data')
        filename = "./data/mcc134_test_" + datetime.datetime.now().strftime(
            "%d-%m-%Y_%H-%M-%S") + ".csv"
        self.csvfile = open(filename, 'w')
        
        mystr = ("Time," + ",".join("TC {}".format(channel) for channel in
                                   range(mcc134.info().NUM_AI_CHANNELS)) +
                 "," + ",".join("CJC {}".format(channel) for channel in
                                range(mcc134.info().NUM_AI_CHANNELS)) +
                 ",Status\n")
        self.csvfile.write(mystr)
        
    def updateInputs(self):
        self.id = None
        if self.device_open:
            self.activity_led.set(1)
            self.activity_id = self.master.after(100, self.activityBlink)
            
            self.current_failures = 0
            logstr = datetime.datetime.now().strftime("%H:%M:%S") + ","
            try:
                for channel in range(mcc134.info().NUM_AI_CHANNELS):
                    # read the tc value
                    self.tc_voltages[channel] = self.board.a_in_read(channel) * 1e6
                    # read the cjc value
                    self.cjc_temps[channel] = self.board.cjc_read(channel)
                    
                    self.watchdog_count = 0
                    
                    if self.baseline_set == True:
                        # compare to limits
                        tc_voltage = self.tc_voltages[channel]
                        if (tc_voltage > self.tc_limit) or (tc_voltage < -self.tc_limit):
                            self.current_failures += 1
                            self.tc_failures[channel] += 1
                            
                        self.cjc_errors[channel] = (self.cjc_temps[channel] -
                            self.baseline_temps[channel])
                        cjc_error = self.cjc_errors[channel]
                        if (cjc_error > self.cjc_limit) or (cjc_error < -self.cjc_limit):
                            self.current_failures += 1
                            self.cjc_failures[channel] += 1
                            
                logstr += (",".join(
                               "{:.1f}".format(value) for value in self.tc_voltages) +
                           "," + ",".join(
                               "{:.1f}".format(value) for value in self.cjc_temps) +
                           ",\n")
                
            except:
                self.software_errors += 1
                self.current_failures += 1
                self.watchdog_count += 1
                logstr += ",,,,,,,,Software error\n"

            self.csvfile.write(logstr)
            self.test_count += 1
            self.updateDisplay()

            if (self.watchdog_check.var.get() == 1 and
                self.watchdog_count >= 5):
                self.board = None
                self.device_open = False
                self.watchdog_count = 0
                self.ready_led.set(0)
                self.master.after(500, self.updateInputs)
            else:
                # schedule another update in 1 s
                self.id = self.master.after(1000, self.updateInputs)
        else:
            # Open the device
            self.initBoard()
            # schedule another attempt
            self.id = self.master.after(500, self.updateInputs)
       
    def updateDisplay(self):
        for channel in range(mcc134.info().NUM_AI_CHANNELS):
            self.tc_voltage_labels[channel].config(
                text="{:.1f}".format(self.tc_voltages[channel]))
            self.tc_failure_labels[channel].config(
                text="{}".format(self.tc_failures[channel]))
            self.cjc_temp_labels[channel].config(
                text="{:.1f}".format(self.cjc_temps[channel]))
            self.cjc_failure_labels[channel].config(
                text="{}".format(self.cjc_failures[channel]))
            self.cjc_error_labels[channel].config(
                text="{:.1f}".format(self.cjc_errors[channel]))
            self.baseline_temp_labels[channel].config(
                text="{:.1f}".format(self.baseline_temps[channel]))
            
        if self.current_failures > 0:
            self.inst_pass_led.set(2)
            self.pass_led.set(2)
        else:
            self.inst_pass_led.set(1)
        self.pass_id = self.master.after(500, self.passBlink)
            
        self.software_error_label.config(
            text="{}".format(self.software_errors))
        self.test_count_label.config(text="{}".format(self.test_count))

    def passBlink(self):
        self.pass_id = None
        self.inst_pass_led.set(0)
        
    def activityBlink(self):
        self.activity_id = None
        self.activity_led.set(0)
        
    # Event handlers
    def close(self):
        if self.id:
            self.master.after_cancel(self.id)
        if self.activity_id:
            self.master.after_cancel(self.activity_id)
        if self.pass_id:
            self.master.after_cancel(self.pass_id)
        self.device_open = False
        if self.csvfile:
            self.csvfile.close()
            self.csvfile = None
        self.master.destroy()


root = Tk()
app = ControlApp(root)
root.mainloop()
