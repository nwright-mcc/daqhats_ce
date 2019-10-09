# MCC DAQ HAT CE Testing Programs

This repository contains CE testing programs and instructions for the MCC DAQ HATs.

## Prerequisites
- Raspbian image (will not work with Raspbian Lite because it requires the graphical OS)
- Raspberry Pi A+, B+, 2, 3 (A+, B, B+), or 4
- Python 3.4 or greater

## Install Instructions

1. Follow the instructions at https://github.com/mccdaq/daqhats for setting up a Raspberry Pi
   and the DAQ HAT at address 0.
2. Open a terminal window and download this repository to your Raspberry Pi:
   ```sh
   cd ~
   git clone https://github.com/nwright-mcc/daqhats_ce.git
   ```
   
## Use Instructions
1. Set up the device to be tested per the test instructions.
2. Use the File Manager program to open the daqhats_ce folder, then open the specific folder
   for the product you are testing (such as 'mcc134').
3. Double-click on the testing program in the folder, and select the "Execute" option if asked.
4. The test program will open then automatically begin operating. See the test instructions
   for specific device test information.
