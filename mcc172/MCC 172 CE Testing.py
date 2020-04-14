#!/usr/bin/env python3
"""
    MCC 172 CE Test application

    Purpose:
        Exercise the MCC 172 for emissions / immunity testing

    Description:
        This app reads and displays the input voltages.
"""
from daqhats import mcc172, SourceType, TriggerModes, OptionFlags
from tkinter import *
import datetime
from tkinter import messagebox
from time import sleep
from math import sqrt
import os
#from tkinter import ttk
from tkinter.ttk import *
#import tkinter.font

DEFAULT_V_LIMIT = 4.985    # mV
SCAN_SAMPLE_COUNT = 20000
SCAN_RATE = 51200         # Hz

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
        master.title("MCC 172 CE Test")
    
        # Initialize variables
        self.device_open = False
        self.board = None
        self.voltage_limit = DEFAULT_V_LIMIT
        self.voltages = [0.0]*mcc172.info().NUM_AI_CHANNELS
        self.failures = [0]*mcc172.info().NUM_AI_CHANNELS
        self.current_failures = 0
        self.test_count = 0
        self.trigger_errors = 0
        self.last_trigger_error = False
        self.software_errors = 0
        self.baseline_set = False
        self.watchdog_count = 0
        self.csvfile = None
        self.id = None
        self.activity_id = None
        self.num_channels = mcc172.info().NUM_AI_CHANNELS

        # GUI Setup

        # Device Frame
        self.device_frame = LabelFrame(master, text="Device status")
        #self.device_frame.pack(side=TOP, expand=False, fill=X)
        self.device_frame.grid(row=0, column=0, padx=3, pady=3,
                               sticky="NEW")
        
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
            self.device_frame, width=8, text="0", relief=SUNKEN, anchor=E)
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
        self.test_frame = LabelFrame(master, text="Test setup")
        self.test_frame.grid(row=0, column=1, rowspan=2,
                             sticky="NEW", padx=3, pady=3)

        # Test widgets
        self.start_button = Button(self.test_frame, text="Start", 
                                  command=self.startTest)
        self.start_button.grid(row=0, column=2, padx=3, pady=3)
        
        label = Label(self.test_frame, text="Sample rate:")
        label.grid(row=1, column=0, padx=3, pady=3, sticky="E")

        style = Style()
        style.configure("C.TButton", foreground='red')
        self.stop_button = Button(self.test_frame, text="Stop", style="C.TButton", #foreground="red",
                                  command=self.stopTest, state=DISABLED)
        self.stop_button.grid(row=1, column=2, padx=3, pady=3, sticky="NSEW")

        v = IntVar()
        self.watchdog_check = Checkbutton(
            self.test_frame, text="Use watchdog", variable=v)
        self.watchdog_check.var = v
        self.watchdog_check.grid(row=0, column=0, columnspan=2, padx=3, pady=3,
                                 sticky="E")

        self.reset_button = Button(self.test_frame, text="Reset",
                                   command=self.resetTest)
        self.reset_button.grid(row=2, column=2, padx=3, pady=3, sticky="NSEW")


        label = Label(self.test_frame, text="Pass/fail (latch):")
        label.grid(row=1, column=0, padx=3, pady=3, sticky="E")
        self.pass_led = LED(self.test_frame, size=20)
        self.pass_led.grid(row=1, column=1, padx=3, pady=3)

        label = Label(self.test_frame, text="Pass/fail (inst):")
        label.grid(row=2, column=0, padx=3, pady=3, sticky="E")
        self.inst_pass_led = LED(self.test_frame, size=20)
        self.inst_pass_led.grid(row=2, column=1, padx=3, pady=3)

        label = Label(self.test_frame, text="Test count:")
        label.grid(row=3, column=0, padx=3, pady=3, sticky="E")
        self.test_count_label = Label(self.test_frame, width=8,
                                      text="0", relief=SUNKEN, anchor=E)
        self.test_count_label.grid(row=3, column=1, padx=3, pady=3)
        

        # Voltage Frame
        self.volt_frame = LabelFrame(master, text="Voltage Inputs, mV")
        #self.tc_frame.pack(side=BOTTOM, expand=True, fill=BOTH)
        self.volt_frame.grid(row=1, column=0, rowspan=2, sticky="NSEW", padx=3, pady=3)

        # Voltage widgets
        label = Label(self.volt_frame, text="Limit: ±")
        label.grid(row=0, column=0, padx=3, pady=3, sticky="E")
        label = Label(self.volt_frame, text="{:.3f}".format(self.voltage_limit),
                      relief=SUNKEN, anchor=E, width=8)
        label.grid(row=0, column=1, padx=3, pady=3, ipadx=2, ipady=2)
        
        label = Label(self.volt_frame, text="Channel")
        label.grid(row=1, column=0, padx=3, pady=3)
        label = Label(self.volt_frame, text="Current")
        label.grid(row=1, column=1, padx=3, pady=3)
        label = Label(self.volt_frame, text="Failures")
        label.grid(row=1, column=2, padx=3, pady=3)
        
        self.voltage_labels = []
        self.failure_labels = []
        
        for index in range(mcc172.info().NUM_AI_CHANNELS):
            # Labels
            label = Label(self.volt_frame, text="{}".format(index))
            label.grid(row=index+2, column=0, padx=3, pady=3)
            #label.grid_configure(sticky="W")
            
            # Voltages
            self.voltage_labels.append(Label(self.volt_frame, width=8, anchor=E,
                                             text="0.0", relief=SUNKEN))
            self.voltage_labels[index].grid(row=index+2, column=1, padx=3,
                                            pady=3, ipadx=2, ipady=2)
            self.voltage_labels[index].grid_configure(sticky="E")

            self.failure_labels.append(Label(self.volt_frame, width=8, anchor=E,
                                             relief=SUNKEN, text="0"))
            self.failure_labels[index].grid(row=index+2, column=2, padx=3,
                                            pady=3, ipadx=2, ipady=2)
            
            
        # Trigger Frame
        self.trigger_frame = LabelFrame(master, text="Trigger Input")
        self.trigger_frame.grid(row=2, column=1, sticky="NSEW", padx=3, pady=3)

        label = Label(self.trigger_frame, text="Failures:")
        label.grid(row=0, column=0, padx=3, pady=3, sticky="E")
        self.trigger_error_label = Label(
            self.trigger_frame, width=8, text="0", relief=SUNKEN, anchor=E)
        self.trigger_error_label.grid(row=0, column=1, padx=3, pady=3,
                                      ipadx=2, ipady=2)

        master.protocol('WM_DELETE_WINDOW', self.close) # exit cleanup

        icon = PhotoImage(file='/usr/share/mcc/daqhats/icon.png')
        master.tk.call('wm', 'iconphoto', master._w, icon)

        self.pass_led.set(1)

        #self.master.after(500, self.establishBaseline)

    def initBoard(self):
        # Try to initialize the device
        try:
            self.board = mcc172(0)
            
            serial = self.board.serial()
            self.serial_number.set(serial)
            
            # turn off IEPE
            self.board.iepe_config_write(0, 0)
            self.board.iepe_config_write(1, 0)
            
            # set ADC clock rate
            self.board.a_in_clock_config_write(SourceType.LOCAL, SCAN_RATE)
            sync = False
            while not sync:
                stat = self.board.a_in_clock_config_read()
                sync = stat.synchronized
                sleep(0.1)

            self.board.trigger_config(SourceType.LOCAL, TriggerModes.RISING_EDGE)
            
            self.ready_led.set(1)
            self.device_open = True
        except:
            self.software_errors += 1
            self.current_failures += 1
   
    def startTest(self):
        self.resetTest()
        
        self.master.after(500, self.establishBaseline)
        # disable controls
        self.start_button.configure(state=DISABLED)
        self.reset_button.configure(state=DISABLED)
        self.stop_button.configure(state=NORMAL)
        self.watchdog_check.configure(state=DISABLED)
    
    def stopTest(self):
        # Stop the test loop
        if self.id:
            self.master.after_cancel(self.id)
        if self.csvfile:
            self.csvfile.close()
            self.csvfile = None
        self.ready_led.set(0)
        # enable controls
        self.start_button.configure(state=NORMAL)
        self.reset_button.configure(state=NORMAL)
        self.stop_button.configure(state=DISABLED)
        self.watchdog_check.configure(state=NORMAL)
    
    def resetTest(self):
        # Reset the error counters and restart
        if self.id:
            self.master.after_cancel(self.id)
        if self.activity_id:
            self.master.after_cancel(self.activity_id)
        #if self.pass_id:
        #    self.master.after_cancel(self.pass_id)

        if self.csvfile:
            self.csvfile.close()
            self.csfvile = None
            
        self.board = None
        self.device_open = False
        self.voltages = [0.0]*mcc172.info().NUM_AI_CHANNELS
        self.failures = [0]*mcc172.info().NUM_AI_CHANNELS
        self.test_count = 0
        self.software_errors = 0
        self.trigger_errors = 0
        self.last_trigger_error = False
        self.baseline_set = False
        self.watchdog_count = 0
        self.pass_led.set(1)
        self.inst_pass_led.set(0)

        self.ready_led.set(0)
        
        self.updateDisplay()
        #self.master.after(500, self.establishBaseline)
            
    def establishBaseline(self):
        self.id = None
        self.current_failures = 0
        
        if self.device_open:
            self.activity_led.set(1)
            self.master.update()
            self.activity_id = self.master.after(100, self.activityBlink)
            
            self.current_failures = 0
            try:
                # Start the first scan
                chan_mask = 2**self.num_channels - 1
                self.board.a_in_scan_start(
                    chan_mask, SCAN_SAMPLE_COUNT, 0)
                
                self.baseline_set = True
                self.watchdog_count = 0
                
                # Create csv file with current date/time in file name
                self.openCsvFile()

                # go to the test loop
                self.id = self.master.after(500, self.updateInputs)
            except FileNotFoundError:
                messagebox.showerror("Error", "Cannot create CSV file")
            except:
                raise
                self.software_errors += 1
                self.current_failures += 1
                self.watchdog_count += 1
                
                # try again
                self.id = self.master.after(500, self.establishBaseline)
                
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
        filename = "./data/mcc172_test_" + datetime.datetime.now().strftime(
            "%d-%m-%Y_%H-%M-%S") + ".csv"
        self.csvfile = open(filename, 'w')
        
        mystr = ("Time," + ",".join("Ch {}".format(channel) for channel in
                                   range(mcc172.info().NUM_AI_CHANNELS)) +
                 ",Status\n")
        self.csvfile.write(mystr)
    
    def calc_rms(self, data, channel, num_channels, num_samples_per_channel):
        """ Calculate RMS value from a block of samples. """
        value = 0.0
        index = channel
        for _i in range(num_samples_per_channel):
            value += (data[index] * data[index]) / num_samples_per_channel
            index += num_channels

        return sqrt(value)
    
    def checkTrigger(self):
        self.id = None
        if self.device_open:
            try:
                # Read the last scan result
                read_result = self.board.a_in_scan_read(0, 0)
                if read_result.triggered:
                    self.trigger_errors += 1
                    self.current_failures += 1
                    self.last_trigger_error = True
                self.board.a_in_scan_cleanup()

                # Start the next scan
                chan_mask = 2**self.num_channels - 1
                self.board.a_in_scan_start(
                    chan_mask, SCAN_SAMPLE_COUNT, 0)
            except:
                raise
                self.board.a_in_scan_stop()
                self.board.a_in_scan_cleanup()

                self.software_errors += 1
                self.current_failures += 1
                self.watchdog_count += 1

            self.id = self.master.after(500, self.updateInputs)
        else:
            # Open the device
            self.initBoard()

            # start a trigger test
            chan_mask = 2**self.num_channels - 1
            self.board.a_in_scan_start(
                chan_mask, SCAN_SAMPLE_COUNT, OptionFlags.EXTTRIGGER)

            self.id = self.master.after(500, self.checkTrigger)
       
    def updateInputs(self):
        self.id = None
        if self.device_open:
            self.activity_led.set(1)
            self.master.update()
            self.activity_id = self.master.after(100, self.activityBlink)
            
            logstr = datetime.datetime.now().strftime("%H:%M:%S") + ","
            
            try:
                # Read the last scan data
                read_result = self.board.a_in_scan_read(SCAN_SAMPLE_COUNT, -1)
                
                # Calculate RMS values
                for channel in range(self.num_channels):
                    self.voltages[channel] = self.calc_rms(
                        read_result.data, channel, self.num_channels, SCAN_SAMPLE_COUNT) * 1e3
                    if self.baseline_set == True:
                        # compare to limits
                        if ((self.voltages[channel] > self.voltage_limit) or
                                (self.voltages[channel] < -self.voltage_limit)):
                            self.current_failures += 1
                            self.failures[channel] += 1
                    
                self.board.a_in_scan_cleanup()

                # Start the next scan
                #chan_mask = 2**self.num_channels - 1
                #self.board.a_in_scan_start(
                #    chan_mask, SCAN_SAMPLE_COUNT, 0)

                # start a trigger test
                chan_mask = 2**self.num_channels - 1
                self.board.a_in_scan_start(
                    chan_mask, SCAN_SAMPLE_COUNT, OptionFlags.EXTTRIGGER)
                
                self.watchdog_count = 0
                            
                logstr += (",".join(
                               "{:.1f}".format(value) for value in self.voltages[:self.num_channels]))
                if self.last_trigger_error:
                    logstr += ",Trigger error\n"
                else:
                    logstr += ",\n"

                self.last_trigger_error = False
            except:
                raise
                self.board.a_in_scan_stop()
                self.board.a_in_scan_cleanup()

                self.software_errors += 1
                self.current_failures += 1
                self.watchdog_count += 1
                logstr += ",,Software error\n"

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
                # schedule another update
                #self.id = self.master.after(1000, self.updateInputs)
                # start the trigger test
                self.id = self.master.after(500, self.checkTrigger)
        else:
            # Open the device
            self.initBoard()
            # schedule another attempt
            #self.id = self.master.after(500, self.updateInputs)

            # start a trigger test
            chan_mask = 2**self.num_channels - 1
            self.board.a_in_scan_start(
                chan_mask, SCAN_SAMPLE_COUNT, OptionFlags.EXTTRIGGER)

            self.id = self.master.after(500, self.checkTrigger)
        
    def updateDisplay(self):
        for channel in range(mcc172.info().NUM_AI_CHANNELS):
            self.voltage_labels[channel].config(
                text="{:.1f}".format(self.voltages[channel]))
            self.failure_labels[channel].config(
                text="{}".format(self.failures[channel]))
            
        if self.current_failures > 0:
            self.inst_pass_led.set(2)
            self.pass_led.set(2)
        else:
            self.inst_pass_led.set(1)
        #self.pass_id = self.master.after(500, self.passBlink)
        self.current_failures = 0
            
        self.trigger_error_label.config(
            text="{}".format(self.trigger_errors))
        self.software_error_label.config(
            text="{}".format(self.software_errors))
        self.test_count_label.config(text="{}".format(self.test_count))

    #def passBlink(self):
    #    self.pass_id = None
    #    self.inst_pass_led.set(0)
        
    def activityBlink(self):
        self.activity_id = None
        self.activity_led.set(0)
        
    # Event handlers
    def close(self):
        if self.board:
            self.board.a_in_scan_stop()
            self.board.a_in_scan_cleanup()
        
        if self.id:
            self.master.after_cancel(self.id)
        if self.activity_id:
            self.master.after_cancel(self.activity_id)
        #if self.pass_id:
        #    self.master.after_cancel(self.pass_id)
        self.device_open = False
        if self.csvfile:
            self.csvfile.close()
            self.csvfile = None
        self.master.destroy()


root = Tk()
app = ControlApp(root)
root.mainloop()
