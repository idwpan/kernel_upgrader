# Python 3+ Linux Kernel Upgrader for Ubuntu systems

Upgrades to the latest stable kernel version displayed on Kernel.org

Tested on Ubuntu 18.10 Server and it worked every time. Still, no promises :)

If you do decide to try this, make sure to read through the code so you understand it, and also make sure to check debug.log even if it looks successful to make sure.

____

### Usage

1. Copy env.template to .env, and replace the value with your user password so the script can run sudo for dpkg
2. Make sure any requried libraries are installed (requirements.txt coming soon)
3. Run the script when ready! No arguments or user input is required, at least for AMD64 systems (to change needs to be done in the code). Just run $ python3 kernel_upgrade.py. Usually takes under 3 minutes or so for me, maybe a little longer.

____

### Example Output

```
$ python3 kernel_upgrade.py 
  If you do not want to upgrade your Kernel, or aren't comfortable using this program, please hit Ctrl+C now.
  * Now sleeping for 15 seconds.
  * Begining Kernel upgrade for Ubuntu
  * The latest stable Linux Kernel version is: v5.1.6
  * Installation Success for Linux-Headers-v5.1.6 (all)
  * Installation Success for Linux-Headers-v5.1.6 (amd64)
  * Installation Success for Linux-Modules-v5.1.6 (amd64)
  * Installation Success for Linux-Image-v5.1.6 (amd64)
  * Looks like all the installations completed successfully!
  * Be sure to skim over ./debug.log to be sure :)
  * Total Time elapsed: 172.93 seconds
```
