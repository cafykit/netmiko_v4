"""CiscoBaseConnection is netmiko SSH class for Cisco and Cisco-like platforms."""
from typing import Optional
import re
import time
import logging
from netmiko.base_connection import BaseConnection
from netmiko.scp_handler import BaseFileTransfer
from netmiko.exceptions import NetmikoAuthenticationException

log = logging.getLogger('netmiko')

class CiscoBaseConnection(BaseConnection):
    """Base Class for cisco-like behavior."""

    def check_enable_mode(self, check_string: str = "#") -> bool:
        """Check if in enable mode. Return boolean."""
        return super().check_enable_mode(check_string=check_string)

    def enable(
        self,
        cmd: str = "enable",
        pattern: str = "ssword",
        enable_pattern: Optional[str] = None,
        re_flags: int = re.IGNORECASE,
    ) -> str:
        """Enter enable mode."""
        return super().enable(
            cmd=cmd, pattern=pattern, enable_pattern=enable_pattern, re_flags=re_flags
        )

    def exit_enable_mode(self, exit_command: str = "disable") -> str:
        """Exits enable (privileged exec) mode."""
        return super().exit_enable_mode(exit_command=exit_command)

    def check_config_mode(self, check_string: str = ")#", pattern: str = "") -> bool:
        """
        Checks if the device is in configuration mode or not.

        Cisco IOS devices abbreviate the prompt at 20 chars in config mode
        """
        return super().check_config_mode(check_string=check_string, pattern=pattern)

    def config_mode(
        self,
        config_command: str = "configure terminal",
        pattern: str = "",
        re_flags: int = 0,
    ) -> str:
        return super().config_mode(
            config_command=config_command, pattern=pattern, re_flags=re_flags
        )

    def exit_config_mode(self, exit_config: str = "end", pattern: str = r"#.*") -> str:
        """Exit from configuration mode."""
        return super().exit_config_mode(exit_config=exit_config, pattern=pattern)

    def serial_login(
        self,
        pri_prompt_terminator: str = r"\#\s*$",
        alt_prompt_terminator: str = r">\s*$",
        username_pattern: str = r"(?:user:|username|login)",
        pwd_pattern: str = r"assword",
        delay_factor: float = 1.0,
        max_loops: int = 20,
    ) -> str:
        self.write_channel(self.TELNET_RETURN)
        output = self.read_channel()
        if re.search(pri_prompt_terminator, output, flags=re.M) or re.search(
            alt_prompt_terminator, output, flags=re.M
        ):
            return output
        else:
            return self.telnet_login(
                pri_prompt_terminator,
                alt_prompt_terminator,
                username_pattern,
                pwd_pattern,
                delay_factor,
                max_loops,
            )

    def telnet_login(
        self,
        pri_prompt_terminator: str = r"\#\s*$",
        alt_prompt_terminator: str = r">\s*$",
        username_pattern: str = r"(?:user:|username|login|user name)",
        pwd_pattern: str = r"assword|ecret",
        delay_factor: float = 1.0,
        max_loops: int = 20,
    ) -> str:
        """Telnet login. Can be username/password or just password."""
        delay_factor = self.select_delay_factor(delay_factor)

        if delay_factor < 1:
            if not self._legacy_mode and self.fast_cli:
                delay_factor = 1

        time.sleep(1 * delay_factor)

        output = ""
        return_msg = ""
        outer_loops = 3
        inner_loops = int(max_loops / outer_loops)
        i = 1
        is_spitfire = False
        for _ in range(outer_loops):
            while i <= inner_loops:
                try:
                    log.debug("Reading channel for the first time")
                    output = self.read_channel()

                    # This below if block is addeed because when the telnet console starts with UserName,
                    # self.read_channel which internally calls telnetlib.read_ver_eager() returns empty string
                    # So, assign it to self.find_prompt()
                    log.debug("Output after reading channel for first time: {}".format(output))
                    if output == '':
                        time.sleep(2 * delay_factor)
                        log.debug("output is empty, doing find_prompt()")
                        output = self.find_prompt()

                    log.debug("Output after doing find_prompt: {}".format(output))
                    return_msg += output

                    # is at spitfire xr prompt
                    if re.search('RP/\d+/RP\d+/CPU\d+:\S*#$', output):
                        return return_msg

                    # At Rebooted BMC prompt
                    # reboot_bmc_to_bmc_cmd = 'boot'
                    rebooted_bmc_prompt_pattern = r"cisco-bmc#"
                    if re.search(rebooted_bmc_prompt_pattern, output):
                        self.write_channel(self.TELNET_RETURN + "boot" + self.TELNET_RETURN)
                        time.sleep(60 * delay_factor)
                        self.write_channel(self.TELNET_RETURN)
                        output = self.read_channel()
                        return_msg += output

                    # At BMC prompt
                    bmc_prompt_pattern = r"root@spitfire-arm:~#"
                    if re.search(bmc_prompt_pattern, output):
                        self.write_channel(self.TELNET_RETURN + "\x17" + self.TELNET_RETURN)
                        time.sleep(1 * delay_factor)
                        output = self.read_channel()
                        return_msg += output

                    # Search for linux host prompt pattern [xr:~] or x86 prompt pattern
                    linux_prompt_pattern = r"(\[xr:~]\$)|(\[[\w\-]+:~\]\$$)"
                    switch_to_xr_command = 'xr'
                    x86_prompt_pattern = r"(\S+@xr:~#)|(\S+@ios:~#)"
                    if re.search(linux_prompt_pattern, output) or re.search(x86_prompt_pattern, output):
                        self.write_channel(self.TELNET_RETURN + "xr" + self.TELNET_RETURN)
                        time.sleep(1 * delay_factor)
                        output = self.read_channel()
                        return_msg += output

                    # If previously from xr prompt, if bash was executed to go to linux host prompt,
                    # then inorder to go back to xr prompt, no need of xrlogin and password,
                    # just do "exit" cmd
                    xr_no_login_pattern = "Exec cannot be started from within an existing exec session"
                    if re.search(xr_no_login_pattern, output):
                        self.write_channel(self.TELNET_RETURN + "exit" + self.TELNET_RETURN)
                        time.sleep(1 * delay_factor)
                        output = self.read_channel()
                        return_msg += output
                        if pri_prompt_terminator in output or alt_prompt_terminator in output:
                            return return_msg

                    # If previously from xr prompt, XR not started, must restart XR
                    xr_not_started = r"(error while loading shared libraries)|(cannot open shared object)"
                    if re.search(xr_not_started, output):
                        self.write_channel("initctl start ios-xr.routing.start" + self.TELNET_RETURN)
                        time.sleep(60 * delay_factor)
                        self.write_channel(self.TELNET_RETURN)
                        output = self.read_channel()
                        return_msg += output

                    # Search for standby console pattern
                    standby_pattern = r"RP Node is not ready or active for login"
                    if re.search(standby_pattern, output):
                        ''' Session is standby state '''
                        return return_msg

                    # Search for username pattern / send username
                    # If the prompt shows "xr login:", the you can directly login to xr using xr username
                    # and password or you can login to linux host, using linux host's username password
                    log.debug("Searching for username pattern")
                    my_password = self.password
                    if re.search(username_pattern, output, flags=re.I):
                        # Sometimes username/password must be terminated with "\r" and not "\r\n"
                        log.debug("Username pattern detected, sending Username={}".format(self.username))
                        time.sleep(1)
                        bmc_login_pattern = "spitfire-arm login:"
                        if re.search(bmc_login_pattern, output):
                            my_password = '0penBmc'
                        else:
                            my_password = self.password
                        self.write_channel(self.username + "\r")
                        time.sleep(1 * delay_factor)
                        output = self.read_channel()
                        return_msg += output
                        log.debug("After sending username, the output pattern is={}".format(output))
                        log.debug("________________________________________________")
                    else:
                        xr_or_host_login_pattern = "xr login:"
                        xr_or_host_login_alt_pattern = "ios login:"
                        if re.search(xr_or_host_login_pattern, output) or re.search(xr_or_host_login_alt_pattern,
                                                                                    output):
                            self.write_channel(self.username + self.TELNET_RETURN)
                            time.sleep(1 * delay_factor)
                            output = self.read_channel()
                            return_msg += output

                    # Search for password pattern / send password
                    if re.search(pwd_pattern, output, flags=re.I):
                        # Sometimes username/password must be terminated with "\r" and not "\r\n"
                        assert isinstance(my_password, str)
                        self.write_channel(my_password + "\r")
                        time.sleep(0.5 * delay_factor)
                        output = self.read_channel()
                        return_msg += output
                        if re.search(pri_prompt_terminator, output, flags=re.M) or \
                                re.search(alt_prompt_terminator, output, flags=re.M) and \
                                not re.search(x86_prompt_pattern, output):
                            return return_msg

                        if re.search(pwd_pattern, output):
                            self.write_channel(my_password + self.TELNET_RETURN)
                            time.sleep(.5 * delay_factor)
                            output = self.read_channel()
                            return_msg += output

                    # Search for "VR0 con0/RP0/CPU0 is now available Press RETURN to get started" pattern
                    # on Sunstone devices
                    sunstone_pattern = r'Press RETURN to get started\.$'
                    if re.search(sunstone_pattern, output):
                        print("*****Sunstone pattern detected")
                        self.write_channel(self.TELNET_RETURN)
                        output = self.read_channel()

                    # Support direct telnet through terminal server
                    if re.search(
                        r"initial configuration dialog\? \[yes/no\]: ", output
                    ):
                        self.write_channel("no" + self.TELNET_RETURN)
                        time.sleep(0.5 * delay_factor)
                        count = 0
                        while count < 15:
                            output = self.read_channel()
                            return_msg += output
                            if re.search(r"ress RETURN to get started", output):
                                output = ""
                                break
                            time.sleep(2 * delay_factor)
                            count += 1

                    # Check for device with no password configured
                    if re.search(r"assword required, but none set", output):
                        assert self.remote_conn is not None
                        self.remote_conn.close()
                        msg = (
                            "Login failed - Password required, but none set: {}".format(
                                self.host
                            )
                        )
                        raise NetmikoAuthenticationException(msg)

                    if re.search(rebooted_bmc_prompt_pattern, output) or \
                            re.search(bmc_prompt_pattern, output) or \
                            re.search(x86_prompt_pattern, output):
                        is_spitfire = True

                    # Check if proper data received
                    if re.search(
                        pri_prompt_terminator, output, flags=re.M
                    ) or re.search(alt_prompt_terminator, output, flags=re.M) and not is_spitfire:
                        return return_msg

                    i += 1

                except EOFError:
                    assert self.remote_conn is not None
                    self.remote_conn.close()
                    msg = f"EOFError Telnet Login failed: {self.host}"
                    raise NetmikoAuthenticationException(msg)

            # Try sending an <enter> to restart the login process
            self.write_channel(self.TELNET_RETURN)
            time.sleep(0.5 * delay_factor)
            i = 1

        # Last try to see if we already logged in
        self.write_channel(self.TELNET_RETURN)
        time.sleep(0.5 * delay_factor)
        output = self.read_channel()
        return_msg += output
        if re.search(pri_prompt_terminator, output, flags=re.M) or re.search(
            alt_prompt_terminator, output, flags=re.M
        ):
            return return_msg

        assert self.remote_conn is not None
        self.remote_conn.close()
        msg = f"Login failed: {self.host}"
        raise NetmikoAuthenticationException(msg)

    def cleanup(self, command: str = "exit") -> None:
        """Gracefully exit the SSH session."""
        try:
            # The pattern="" forces use of send_command_timing
            if self.check_config_mode(pattern=""):
                self.exit_config_mode()
        except Exception:
            pass
        # Always try to send final 'exit' (command)
        if self.session_log:
            self.session_log.fin = True
        self.write_channel(command + self.RETURN)

    def _autodetect_fs(
        self, cmd: str = "dir", pattern: str = r"Directory of (.*)/"
    ) -> str:
        """Autodetect the file system on the remote device. Used by SCP operations."""
        if not self.check_enable_mode():
            raise ValueError("Must be in enable mode to auto-detect the file-system.")
        output = self._send_command_str(cmd)
        match = re.search(pattern, output)
        if match:
            file_system = match.group(1)
            # Test file_system
            cmd = f"dir {file_system}"
            output = self._send_command_str(cmd)
            if "% Invalid" in output or "%Error:" in output:
                raise ValueError(
                    "An error occurred in dynamically determining remote file "
                    "system: {} {}".format(cmd, output)
                )
            else:
                return file_system

        raise ValueError(
            "An error occurred in dynamically determining remote file "
            "system: {} {}".format(cmd, output)
        )

    def save_config(
        self,
        cmd: str = "copy running-config startup-config",
        confirm: bool = False,
        confirm_response: str = "",
    ) -> str:
        """Saves Config."""
        self.enable()
        if confirm:
            output = self._send_command_timing_str(
                command_string=cmd, strip_prompt=False, strip_command=False
            )
            if confirm_response:
                output += self._send_command_timing_str(
                    confirm_response, strip_prompt=False, strip_command=False
                )
            else:
                # Send enter by default
                output += self._send_command_timing_str(
                    self.RETURN, strip_prompt=False, strip_command=False
                )
        else:
            # Some devices are slow so match on trailing-prompt if you can
            output = self._send_command_str(
                command_string=cmd, strip_prompt=False, strip_command=False
            )
        return output


class CiscoSSHConnection(CiscoBaseConnection):
    pass


class CiscoFileTransfer(BaseFileTransfer):
    pass
