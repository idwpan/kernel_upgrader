#!/usr/bin/env python3
import logging, logging.config
import os
import requests
import signal
import sys
import time

from bs4 import BeautifulSoup
from pathlib import Path
from dotenv import load_dotenv
from subprocess import Popen, PIPE


def signal_handler(sig, frame):
    """Exit on Ctrl+C

    Todo: Make less dangerous if interrupted during install.

    """
    print('You pressed Ctrl+C!')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

logging.config.fileConfig('./logging_config.ini')

# Pull sudo pass from .env file.
ENV_PATH = Path('.') / '.env'
load_dotenv(dotenv_path=ENV_PATH)
SUDO_PASS = os.getenv('SUDO_PASS')


def soupify(url):
    """Perform GET request and load into BeautifulSoup"""
    r = requests.get(url)
    return BeautifulSoup(r.text, 'html.parser')

class Kernel:
    """Class to handle fetching of latest kernel version

    Params:
        URL (str): URL to kernel.org
        major (int): Linux "major" version part. (ie: {5}.1.6)
        minor (int): Linux "minor" version part. (ie: 5.{1}.6)
        revision (int): Linux "revision" version part. (ie: 5.1.{6})
        ver_lst (list): [major, minor, revision]
        ver_str (str): (ex:) "5.1.6"

    """
    def __init__(self):
        self.URL = "https://kernel.org/"
        self._update()

    def _update(self):
        """Update class vars"""
        self.major, self.minor, self.revision = self._fetch_latest()
        self.ver_lst = [self.major, self.minor, self.revision]
        self.ver_str = '.'.join(self.ver_lst)
        logging.info(f"The latest stable Linux Kernel version is: v{self.ver_str}")

    def _fetch_latest(self):
        """Get latest Linux version number

        Returns:
            tuple: (major, minor, revision)

        """
        soup = soupify(self.URL)
        kernel_ver = soup.find("td", {"id": "latest_link"}).getText().strip().split('.')
        return tuple(kernel_ver)

    def get_latest_ver(self):
        """Displays latest version string.

        Returns:
            str: (ex:) "5.1.6"

        """
        return self.ver_str


class Upgrade(Kernel):
    """Class to handle finding, downloading, and installing the kernel files

    Child-class to Kernel() so only one object needs to be initialized to
    begin the upgrade. When Upgrade() is initialized, it runs through the
    kernel version fetching, and saves to Upgrade().kernel_version

    """
    def __init__(self):
        """Fetch kernel version, then list of required .deb files, then install them"""
        Kernel.__init__(self)
        self.URL = "https://kernel.ubuntu.com/~kernel-ppa/mainline"
        self.return_codes = [False, False, False, False]
        self.kernel_version = Kernel.get_latest_ver(self)
        self.packages = self.fetch_deb_lst()
        self.install_all_debs()


    def fetch_deb_lst(self, arch="amd64"):
        """Pulls the Ubuntu page with the required files, and parses it.

        Args:
            (optional) arch (str): Archetecture of the files to get. Default "amd64"

        Returns:
            list: of required .deb filenames to install

        """
        out = []

        soup = soupify(f"{self.URL}/v{self.kernel_version}/")
        tag = soup.find('body').find('code')
        links = tag.find_all('a', href=True)

        for ittr, link in enumerate(links):
            if ((arch in link.text and "BUILD.LOG" not in link.text) or \
               (arch in links[ittr-1].text and "all" in link.text)) and \
               ("lowlatency" not in link.text):
                out.append(link.text)
        return self._deb_sort(out)


    def _deb_sort(self, files):
        """Files need to be installed in a certain order.

        1. Linux Headers ... all.deb
        2. Linux Headers ... amd64.deb
        3. Linux Modules ... amd64.deb
        4. Linux Image ... amd64.deb

        Args:
            files (list): list of .deb filenames

        Returns:
            tuple: of sorted .deb filenames

        """
        out = [None, None, None, None]
        for f in files:
            if "headers" in f and "all" in f:
                out[0] = f
            elif "headers" in f and "generic" in f:
                out[1] = f
            elif "modules" in f and "generic" in f:
                out[2] = f
            elif "image" in f and "generic" in f:
                out[3] = f

        logging.debug("Files queued for installation:")
        for i,o in enumerate(out):
            logging.debug(f"{i+1}. {self._shorten_name(o)}")
        return tuple(out)

    def get_deb(self, deb):
        """Request .deb file via GET request, then write data to a file on disk.

        Args:
            deb (str): .deb filename to download

        """
        logging.debug(f"Download Start - ({self._shorten_name(deb)})...")
        t = time.perf_counter()
        f = self._get_pkg_data(deb)
        w = self._write_pkg_data(f)
        e = time.perf_counter() - t
        logging.debug(f"Download End - Time elapsed: {e:0.2f} seconds")


    def install_all_debs(self):
        """Wrapper to install all .debs required"""
        for deb in self.packages:
            self.get_deb(deb)
            self.install_deb(deb)


    def install_deb(self, deb):
        """Installs .deb file and checks return code

        Args:
            deb (str): .deb filename to install
        """
        logging.debug(f"Installation Start - ({self._shorten_name(deb)})...")
        t = time.perf_counter()
        rc = self._install_deb(deb)
        e = time.perf_counter() - t
        logging.debug(f"Installation End - Time elapsed: {e:0.2f} seconds")
        self._rc_check(rc, deb)


    def _install_deb(self, filename):
        """Runs the dpkg command to install the .deb file

        Args:
            filename (str): name of file to install

        Returns:
            int: return code of dpkg attempt

        """
        command = f"dpkg -i ./{filename}".split()
        p = Popen(['sudo', '-S'] + command, stdout=PIPE, stdin=PIPE, stderr=PIPE, universal_newlines=True)
        sudo_prompt = p.communicate(SUDO_PASS + '\n')[1]
        rc = p.poll()
        logging.debug(f"{self._shorten_name(filename)} install return code: {rc}")
        return rc


    def _rc_check(self, rc, deb_name):
        """Handles logging if dpkg return code is not zero

        Args:
            rc (int): return code
            deb_name (str): Name of deb file return code is for

        """
        if rc == 0:
            logging.info(f"Installation Success for {self._shorten_name(deb_name)}")
            self.return_codes[self.packages.index(deb_name)] = True
            logging.debug(f"Packages index for {self._shorten_name(deb_name)}: {self.packages.index(deb_name)}")
            logging.debug(f"RCs: {self.return_codes}")
        else:
            logging.warning("!!! Installation may have failed.")
            logging.warning(f"dpkg return code: {rc}")
            logging.warning("Please see ./kern_upgrade.log for debugging information.")



    def _shorten_name(self, filename):
        """Strips a lot of the numbers from the file names so it's easier to read.

        Args:
            filename (str): Name to shorten

        Returns:
            str: shortened filename

        """
        base = filename.split('-')

        if "unsigned" in base[2]:
            _ver = base[3]
        else:
            _ver = base[2]

        ver = f"v{_ver}"
        package = base[1].capitalize()
        arch = base[-1].split('_')[1].split('.')[0]
        short_name = f"Linux-{package}-{ver} ({arch})"
        return short_name

    def _delete_file(self, filename):
        """Removes a file from the file system

        Args:
            filename (str): name of file to delete in current directory

        """
        os.remove(f"./{filename}")
        logging.debug(f"Deleted existing file: {self._shorten_name(filename)}")

    def _file_exists(self, filename):
        """Checks if a file path exists or not

        Args:
            filename (str): name of file to check existence

        Returns:
            bool: true if exists, false if not"""
        if os.path.exists(f"./{filename}"):
            logging.debug(f"File exists: {self._shorten_name(filename)}")
            return True
        else:
            return False

    def _get_pkg_data(self, filename):
        """Sends the GET request to download the .deb file contents

        Args:
            filename (str): name of file to request from Ubuntu kernel site

        Returns:
            tuple: (filename (str), file_content (str)

        """
        if self._file_exists(filename):
            self._delete_file(filename)
        return filename, requests.get(f"{self.URL}/v{self.kernel_version}/{filename}").content

    def _write_pkg_data(self, fetch_resp):
        """Writes GET response contents to a file

        Args:
            fetch_resp (tuple): (filename (str), file_contents (str))

        """
        name, resp = fetch_resp
        with open(name, 'wb') as f:
            f.write(resp)
        f.close()

def double_check():
    """Pauses for 15 seconds to allow the user to exit before initiating a Kernel upgrade"""
    logging.warning("If you do not want to upgrade your Kernel, or aren't comfortable using this program, please hit Ctrl+C now.")
    logging.warning("Now sleeping for 15 seconds.")
    time.sleep(15)


def main():
    """Main function to run a Kernel upgrade for Ubuntu"""

    # safety first
    double_check()

    logging.info(f"Begining Kernel upgrade for Ubuntu")
    start_time = time.perf_counter()

    u = Upgrade()

    if all(u.return_codes):
        logging.info("Looks like all the installations completed successfully!")
        logging.info("Be sure to skim over ./debug.log to be sure :)")
    else:
        logging.warning("Uh-oh, one or more of the package installations failed...")
        logging.warning("Check ./debug.log for more details.")

    elapsed = time.perf_counter() - start_time

    logging.info(f"Total Time elapsed: {elapsed:0.2f} seconds")

if __name__ == '__main__':
    main()
