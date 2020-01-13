#!/usr/bin/env python3
"""
    MCC 152 CE Test application

    Purpose:
        Exercise the MCC 152 for emissions / immunity testing

    Description:
        This app reads and displays the input voltages.
"""
from daqhats import mcc152, DIOConfigItem
from tkinter import *
import datetime
from tkinter import messagebox
import os
import Gpib
import random
#from tkinter import ttk
from tkinter.ttk import *
#import tkinter.font

DEFAULT_V_LIMIT = 50   # mV

#******************************************************************************
# HP 34401A DMM
class DMM:
    def __init__(self):
        self.device = Gpib.Gpib(0, 5)
        # first write after reboot fails so add a retry mechanism
        self.device.timeout(9)  # 100 ms
        written = False
        while not written:
            try:
                self.device.write("*CLS")
            except:
                pass
            else:
                written = True
                self.device.timeout(13)
        
        self.device.write("INP:IMP:AUTO ON")
        self.device.write("CONF:VOLT:DC")
        return
    
    def __del__(self):
        self.device.ibloc()
        
    def read_voltage(self, resolution, range=0):
        if resolution == 0:
            self.device.write(":MEAS:VOLT:DC? DEF,DEF")
        else:
            if range == 0:
                self.device.write(":MEAS:VOLT:DC? DEF,MIN")
            else:
                self.device.write(":MEAS:VOLT:DC? MIN,MIN")
        
        result = self.device.read()
        
        value = float(result)
        return value
    
    def display(self, string):
        self.device.write("DISP:TEXT \"{0:s}\"".format(string))
        return

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
        master.title("MCC 152 CE Test")
    
        # Initialize variables
        self.device_open = False
        self.board = None
        self.voltage_limit = DEFAULT_V_LIMIT
        self.ao_voltage = mcc152.info().AO_MAX_VOLTAGE
        self.test_count = 0
        self.software_errors = 0
        self.baseline_set = False
        self.watchdog_count = 0
        self.csvfile = None
        self.id = None
        self.activity_id = None
        self.d_out_values = [0]*4
        self.d_in_values = [0]*4
        
        self.dmm = DMM()

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
        label = Label(self.test_frame, text="Pass/fail (latch):")
        label.grid(row=0, column=0, padx=3, pady=3, sticky="W")
        self.pass_led = LED(self.test_frame, size=20)
        self.pass_led.grid(row=0, column=1, padx=3, pady=3)

        label = Label(self.test_frame, text="Pass/fail (inst):")
        label.grid(row=1, column=0, padx=3, pady=3, sticky="W")
        self.inst_pass_led = LED(self.test_frame, size=20)
        self.inst_pass_led.grid(row=1, column=1, padx=3, pady=3)

        label = Label(self.test_frame, text="Test count:")
        label.grid(row=2, column=0, padx=3, pady=3, sticky="W")
        self.test_count_label = Label(self.test_frame, width=8,
                                      text="0", relief=SUNKEN, anchor=E)
        self.test_count_label.grid(row=2, column=1, padx=3, pady=3, ipadx=2, ipady=2)
        

        self.start_button = Button(self.test_frame, text="Start", 
                                  command=self.startTest)
        self.start_button.grid(row=0, column=2, padx=3, pady=3)
        
        style = Style()
        style.configure("C.TButton", foreground='red')
        self.stop_button = Button(self.test_frame, text="Stop", style="C.TButton", #foreground="red",
                                  command=self.stopTest, state=DISABLED)
        self.stop_button.grid(row=1, column=2, padx=3, pady=3, sticky="NSEW")

        self.reset_button = Button(self.test_frame, text="Reset",
                                   command=self.resetTest)
        self.reset_button.grid(row=2, column=2, padx=3, pady=3, sticky="NSEW")

        v = IntVar()
        self.watchdog_check = Checkbutton(
            self.test_frame, text="Use watchdog", variable=v)
        self.watchdog_check.var = v
        self.watchdog_check.grid(row=3, column=0, columnspan=2, padx=3, pady=3,
                                 sticky="W")

        # Digital I/O Frame
        self.dio_frame = LabelFrame(master, text="Digital I/O Loopback")
        self.dio_frame.grid(row=1, rowspan=2, column=0, sticky="NSEW", padx=3, pady=3)
        
        # Widgets
        label = Label(self.dio_frame, text="Limit: No mismatch")
        label.grid(row=0, column=0, columnspan=6, padx=3, pady=3, sticky="W")
        
        label = Label(self.dio_frame, text="Channel")
        label.grid(row=1, column=0, padx=3, pady=3)
        label = Label(self.dio_frame, text="State")
        label.grid(row=1, column=1, padx=3, pady=3)
        label = Label(self.dio_frame, text="Value")
        label.grid(row=1, column=2, padx=3, pady=3)
        label = Label(self.dio_frame, text="Channel")
        label.grid(row=1, column=3, padx=3, pady=3)
        label = Label(self.dio_frame, text="State")
        label.grid(row=1, column=4, padx=3, pady=3)
        label = Label(self.dio_frame, text="Value")
        label.grid(row=1, column=5, padx=3, pady=3)
        label = Label(self.dio_frame, text="Failures")
        label.grid(row=1, column=6, padx=3, pady=3)

        self.dio_failure_labels = []
        self.d_out_labels = []
        self.d_in_labels = []
        
        for channel in range(4):
            label = Label(self.dio_frame, text=channel)
            label.grid(row=2+channel, column=0, padx=3, pady=3)
            label = Label(self.dio_frame, text=channel+4)
            label.grid(row=2+channel, column=3, padx=3, pady=3)

            label = Label(self.dio_frame, text="Out", width=4, anchor=CENTER,
                          relief=SUNKEN)
            label.grid(row=2+channel, column=1, padx=3, pady=3, ipadx=2, ipady=2)

            self.d_out_labels.append(Label(self.dio_frame, text="", width=3, anchor=CENTER,
                                           relief=SUNKEN))
            self.d_out_labels[channel].grid(row=2+channel, column=2, padx=3, pady=3, ipadx=2, ipady=2)

            label = Label(self.dio_frame, text="In", width=4, anchor=CENTER,
                          relief=SUNKEN)
            label.grid(row=2+channel, column=4, padx=3, pady=3, ipadx=2, ipady=2)

            self.d_in_labels.append(Label(self.dio_frame, text="", width=3, anchor=CENTER,
                                          relief=SUNKEN))
            self.d_in_labels[channel].grid(row=2+channel, column=5, padx=3, pady=3, ipadx=2, ipady=2)

            self.dio_failure_labels.append(Label(self.dio_frame, width=8, anchor=E,
                                                 relief=SUNKEN, text="0"))
            self.dio_failure_labels[channel].grid(row=2+channel, column=6, padx=3,
                                            pady=3, ipadx=2, ipady=2)


        # Output Voltage Frame
        self.volt_frame = LabelFrame(master, text="Voltage Output")
        #self.tc_frame.pack(side=BOTTOM, expand=True, fill=BOTH)
        self.volt_frame.grid(row=2, column=1, sticky="NSEW", padx=3, pady=3)

        # Voltage widgets
        label = Label(self.volt_frame, text="Limit: ±")
        label.grid(row=0, column=0, padx=3, pady=3, sticky="W")
        label = Label(self.volt_frame, text="{:.1f} mV".format(self.voltage_limit),
                      relief=SUNKEN, anchor=E, width=10)
        label.grid(row=0, column=1, padx=3, pady=3, ipadx=2, ipady=2)
        
        label = Label(self.volt_frame, text="Output, V")
        label.grid(row=1, column=0, padx=3, pady=3)        
        label = Label(self.volt_frame, text="Error, mV")
        label.grid(row=1, column=1, padx=3, pady=3)
        label = Label(self.volt_frame, text="Failures")
        label.grid(row=1, column=2, padx=3, pady=3)
        
        self.voltage_label = None
        self.error_voltage_label = None
        self.ao_failure_label = None
        
        # Voltage
        self.voltage_label = Label(self.volt_frame, anchor=E, width=10,
                                   text="", relief=SUNKEN)
        self.voltage_label.grid(row=2, column=0, padx=3, pady=3, ipadx=2, ipady=2)
        
        self.error_voltage_label = Label(self.volt_frame, anchor=E, width=10,
                                         text="", relief=SUNKEN)
        self.error_voltage_label.grid(row=2, column=1, padx=3,
                                pady=3, ipadx=2, ipady=2)
        #self.voltage_label.grid_configure(sticky="E")

        self.ao_failure_label = Label(self.volt_frame, anchor=E, width=10,
                                      relief=SUNKEN, text="0")
        self.ao_failure_label.grid(row=2, column=2, padx=3,
                                pady=3, ipadx=2, ipady=2)
            
        self.volt_frame.grid_columnconfigure(0, weight=1)
        self.volt_frame.grid_columnconfigure(1, weight=1)
        self.volt_frame.grid_columnconfigure(2, weight=1)
            
        master.protocol('WM_DELETE_WINDOW', self.close) # exit cleanup

        icon = PhotoImage(file='/usr/share/mcc/daqhats/icon.png')
        master.tk.call('wm', 'iconphoto', master._w, icon)

        self.pass_led.set(1)

        #self.master.after(500, self.establishBaseline)

    def initBoard(self):
        # Try to initialize the device
        try:
            self.board = mcc152(0)
            
            serial = self.board.serial()
            self.serial_number.set(serial)
            
            # set DIO states and values
            self.board.dio_reset()
            self.board.dio_config_write_port(DIOConfigItem.DIRECTION, 0xF0)
            self.board.dio_output_write_port(0x00)
            self.d_out_values = [0]*4

            self.d_in_values = [0]*4
            for index in range(4):
                self.d_in_values[index] = self.board.dio_input_read_bit(index+4)
        
            # set analog output values
            self.board.a_out_write_all([self.ao_voltage, self.ao_voltage])
            
            self.ready_led.set(1)
            self.device_open = True
        except:
            self.software_errors += 1
            self.current_failures += 1
   
    def startTest(self):
        self.resetTest()
        # get control values

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
        self.test_count = 0
        self.software_errors = 0
        self.baseline_set = False
        self.watchdog_count = 0
        self.dio_errors = [0]*4
        self.ao_errors = 0
        self.ao_error_voltage = 0.0
        self.current_failures = 0
        
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
        filename = "./data/mcc152_test_" + datetime.datetime.now().strftime(
            "%d-%m-%Y_%H-%M-%S") + ".csv"
        self.csvfile = open(filename, 'w')
        
        mystr = ("Time," + ",".join("DOut {}".format(value) for value in range(4)) +
                 "," + ",".join("DIn {}".format(value) for value in range(4, 8)) +
                 ",AO 0,Status\n")
        self.csvfile.write(mystr)
        
    def updateInputs(self):
        self.id = None
        if self.device_open:
            self.activity_led.set(1)
            self.master.update()
            self.activity_id = self.master.after(100, self.activityBlink)
            
            self.current_failures = 0
            logstr = datetime.datetime.now().strftime("%H:%M:%S") + ","
            
            try:
                # read the digital inputs and outputs
                for index in range(4):
                    self.d_out_values[index] = self.board.dio_output_read_bit(index)
                    self.d_in_values[index] = self.board.dio_input_read_bit(index+4)
                    if self.d_in_values[index] != self.d_out_values[index]:
                        self.dio_errors[index] += 1
                        self.current_failures += 1
                        
                    # set a new output value for next time
                    self.board.dio_output_write_bit(index, random.getrandbits(1))
                    
                # read the DMM
                dmm_voltage = self.dmm.read_voltage(0)
                self.ao_error_voltage = dmm_voltage - self.ao_voltage
                if abs(self.ao_error_voltage * 1000.0) > self.voltage_limit:
                    self.ao_errors += 1
                    self.current_failures += 1
                    
                self.watchdog_count = 0
                            
                logstr += (",".join(
                               "{}".format(value) for value in self.d_out_values) + "," +
                           ",".join(
                               "{}".format(value) for value in self.d_in_values) +
                           ",{:.6f},\n".format(dmm_voltage))
                
            except:
                self.software_errors += 1
                self.current_failures += 1
                self.watchdog_count += 1
                logstr += ",,,,,,,,,Software error\n"

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
        for index in range(4):
            self.d_out_labels[index].config(
                text="{}".format(self.d_out_values[index]))
            self.d_in_labels[index].config(
                text="{}".format(self.d_in_values[index]))
            self.dio_failure_labels[index].config(
                text="{}".format(self.dio_errors[index]))

        self.voltage_label.config(text="{:.3f}".format(self.ao_voltage))
        self.error_voltage_label.config(text="{:.3f}".format(self.ao_error_voltage * 1000.0))
        self.ao_failure_label.config(text="{}".format(self.ao_errors))
        
        if self.current_failures > 0:
            self.inst_pass_led.set(2)
            self.pass_led.set(2)
        else:
            self.inst_pass_led.set(1)
        #self.pass_id = self.master.after(500, self.passBlink)
            
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
            pass
        
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
