# MCC 152 GPIB setup

The MCC 152 test uses a USB-488 GPIB interface connected to a USB
port to control an external DMM for reading an analog output channel.
These instructions describe how to set up the GPIB software.

## Install Instructions

1. Open a terminal window and run the majority of the following commands
   as root. Update the system.
   ```sh
   sudo bash
   apt update
   apt upgrade -y
   ```
2. Install the rpi-source package and dependencies to get the kernel source
   code.
   ```sh
   apt install -y git bc bison flex libssl-dev
   wget https://raw.githubusercontent.com/notro/rpi-source/master/rpi-source -O /usr/bin/rpi-source && sudo chmod +x /usr/bin/rpi-source && /usr/bin/rpi-source -q --tag-update
   rpi-source
   ```
3. Install libraries and additional packages.
   ```sh
   apt install -y tk-dev build-essential texinfo texi2html libcwidget-dev libncurses5-dev libx11-dev binutils-dev bison flex libusb-1.0-0 libusb-dev libmpfr-dev libexpat1-dev tofrodos subversion autoconf automake libtool mercurial
   ```
4. Download linux-gpib.
   ```sh
   mkdir linux-gpib
   cd linux-gpib
   svn checkout svn://svn.code.sf.net/p/linux-gpib/code/trunk linux-gpib-code
   ```
5. Build the kernel module.
   ```sh
   cd linux-gpib-code/linux-gpib-kernel
   make
   make install
   ldconfig
   ```
6. Build and install the user code.
   ```sh
   cd ../linux-gpib-user
   ./bootstrap
   ./configure --sysconfdir=/etc
   make
   make install
   ldconfig
   cp util/templates/gpib.conf /usr/local/etc/gpib.conf
   ```
7. Ensure the USB GPIB interface is connected to USB then verify driver install.
   ```sh
   lsusb
   ```
   You should see a National Instruments device listed.
8. Check if the module can be loaded.
   ```sh
   modprobe ni_usb_gpib
   ```
9. Modify /usr/local/etc/gpib.conf to set the board_type to "ni_usb_b".
10. Create a gpib group and add the pi user to the group.
    ```ssh
    groupadd gpib
    usermod -a -G gpib pi
    ```
11. Verify that gpib_config runs without errors.
12. Add /usr/local/sbin/gpib_config to /etc/rc.local so it runs during every
    boot.
13. Reboot (exiting root mode)
14. Connect the DMM at address 5 to the GPIB interface, then use
    ibtest to verify operation.
    ```
    ibtest

    d (open a device)
    5 (enter the address)
    w (write string)
    *IDN?
    r (read string)
    q
    ```
    Verify that the received ID string looks correct.
15. Install the python library.
    ```sh
    sudo apt install -y python-dev
    cd ~/linux-gpib/linux-gpib-code/linux-gpib-user/language/python
    sudo python3 ./setup.py install
    ```
16. Perform a python test using the following python code.
    ```python
    import sys
    import Gpib
    inst = Gpib.Gpib(0, 5)
    inst.write("*IDN?")
    result=inst.read()
    print(result)
    ```

