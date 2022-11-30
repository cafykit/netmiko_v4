from __future__ import print_function
from __future__ import unicode_literals
from logger.cafylog import CafyLog
from netmiko.cisco_base_connection import CiscoBaseConnection
from netmiko.exceptions import NetMikoAuthenticationException
from netmiko.utilities import calc_old_timeout
from typing import Optional
import re
import time
import warnings

log = CafyLog()


class CiscoBsp(CiscoBaseConnection):
    """
    CiscoBsp is based of CiscoBaseConnection
    """

    def bmc_to_bsp_prompt(self, bmc_prompt_pattern=r'\s*\#', bsp_prompt_pattern=r']\s*\#', delay_factor=1,
                          max_loops=20, read_timeout=10.0):
        """
        Switch from BMC to BSP prompt

        :param bmc_prompt_pattern: expected BMC prompt
        :param bsp_prompt_pattern: expected BSP prompt
        :param delay_factor: Factor to adjust delays
        :param max_loops: max number of iterations for attempting to switch prompts
        :param read_timeout: maximum time to wait looking for prompt
        :return:
        """

        self.TELNET_RETURN = '\n'
        bmc_to_bsp_cmd = "/usr/local/bin/sol.sh"

        delay_factor = self.select_delay_factor(delay_factor)
        if self.delay_factor_compat:
            # For compatibility calculate the old equivalent read_timeout
            # i.e. what it would have been in Netmiko 3.x
            if delay_factor is None:
                tmp_delay_factor = self.global_delay_factor
            else:
                tmp_delay_factor = self.select_delay_factor(delay_factor)
            compat_timeout = calc_old_timeout(
                max_loops=max_loops,
                delay_factor=tmp_delay_factor,
                loop_delay=0.2,
                old_timeout=self.timeout,
            )
            msg = f"""\n
        You have chosen to use Netmiko's delay_factor compatibility mode for
        send_command. This will revert Netmiko to behave similarly to how it
        did in Netmiko 3.x (i.e. to use delay_factor/global_delay_factor and
        max_loops).

        Using these parameters Netmiko has calculated an effective read_timeout
        of {compat_timeout} and will set the read_timeout to this value.

        Please convert your code to that new format i.e.:

            net_connect.send_command(cmd, read_timeout={compat_timeout})

        And then disable delay_factor_compat.

        delay_factor_compat will be removed in Netmiko 5.x.\n"""
            warnings.warn(msg, DeprecationWarning)

            # Override the read_timeout with Netmiko 3.x way :-(
            read_timeout = compat_timeout

        else:
            # No need for two deprecation messages so only display this if not using
            # delay_factor_compat
            if delay_factor is not None or max_loops is not None:
                msg = """\n
        Netmiko 4.x has deprecated the use of delay_factor/max_loops with
        send_command. You should convert all uses of delay_factor and max_loops
        over to read_timeout=x where x is the total number of seconds to wait
        before timing out.\n"""
                warnings.warn(msg, DeprecationWarning)

        start_time = time.time()
        output = self.find_prompt()
        while time.time() - start_time < read_timeout:
            if re.search(bmc_prompt_pattern, output):
                log.debug("On BMC Prompt")
                log.debug("Sol.sh to enter BSP prompt")
                self.write_channel(bmc_to_bsp_cmd)
                self.write_channel(self.TELNET_RETURN)
                output = self.find_prompt()

            if re.search(bsp_prompt_pattern, output):
                log.debug("On BSP Prompt")
                return

        if not re.search(bsp_prompt_pattern, output):
            raise ValueError(f"BMC to BSP login failed. Prompt received after {max_loops} max loops is {repr(output)}")

    def bsp_to_bmc_prompt(self, bmc_prompt_pattern=r'\s*\#', bsp_prompt_pattern=r']\s*\#', delay_factor=1,
                          max_loops=20, read_timeout=10.0):
        """
        Switch from BSP to BMC prompt

        :param bmc_prompt_pattern: expected BMC prompt
        :param bsp_prompt_pattern: expected BSP prompt
        :param delay_factor: Factor to adjust delays
        :param max_loops: max number of iterations for attempting to switch prompts
        :param read_timeout: maximum time to wait looking for prompt
        :return:
        """

        self.TELNET_RETURN = '\n'
        CTRL_L = "\x0c"

        if self.delay_factor_compat:
            # For compatibility calculate the old equivalent read_timeout
            # i.e. what it would have been in Netmiko 3.x
            if delay_factor is None:
                tmp_delay_factor = self.global_delay_factor
            else:
                tmp_delay_factor = self.select_delay_factor(delay_factor)
            compat_timeout = calc_old_timeout(
                max_loops=max_loops,
                delay_factor=tmp_delay_factor,
                loop_delay=0.2,
                old_timeout=self.timeout,
            )
            msg = f"""\n
        You have chosen to use Netmiko's delay_factor compatibility mode for
        send_command. This will revert Netmiko to behave similarly to how it
        did in Netmiko 3.x (i.e. to use delay_factor/global_delay_factor and
        max_loops).

        Using these parameters Netmiko has calculated an effective read_timeout
        of {compat_timeout} and will set the read_timeout to this value.

        Please convert your code to that new format i.e.:

            net_connect.send_command(cmd, read_timeout={compat_timeout})

        And then disable delay_factor_compat.

        delay_factor_compat will be removed in Netmiko 5.x.\n"""
            warnings.warn(msg, DeprecationWarning)

            # Override the read_timeout with Netmiko 3.x way :-(
            read_timeout = compat_timeout

        else:
            # No need for two deprecation messages so only display this if not using
            # delay_factor_compat
            if delay_factor is not None or max_loops is not None:
                msg = """\n
        Netmiko 4.x has deprecated the use of delay_factor/max_loops with
        send_command. You should convert all uses of delay_factor and max_loops
        over to read_timeout=x where x is the total number of seconds to wait
        before timing out.\n"""
                warnings.warn(msg, DeprecationWarning)

        start_time = time.time()

        output = self.find_prompt()
        while time.time() - start_time < read_timeout:
            if re.search(bsp_prompt_pattern, output):
                log.debug("On BSP Prompt")
                log.debug("Ctrl + L; press X to enter BMC prompt")
                self.write_channel(CTRL_L)
                self.write_channel('x' + self.TELNET_RETURN)
                output = self.find_prompt()

            if re.search(bmc_prompt_pattern, output):
                log.debug("On BMC Prompt")
                return

        if not re.search(bmc_prompt_pattern, output):
            raise ValueError(f"BSP to BMC login failed. Prompt received after {max_loops} max loops is {repr(output)}")

    def bmc_login(self, prompt_pattern=r'\s*\#', username_pattern='login', pwd_pattern=r'assword', delay_factor=1,
                  max_loops=20, read_timeout=10.0):
        """
        Handle BMC login prompt

        :param prompt_pattern: expected BMC prompt
        :param username_pattern: username prompt pattern
        :param pwd_pattern: password prompt pattern
        :param delay_factor: Factor to adjust delays
        :param max_loops: max number of iterations for attempting to login to BMC prompt before raising exception
        :param read_timeout: maximum time to wait looking for pattern
        :return:
        """

        bmc_username = "root"
        bmc_pass = "0penBmc"
        self.TELNET_RETURN = '\n'

        if self.delay_factor_compat:
            # For compatibility calculate the old equivalent read_timeout
            # i.e. what it would have been in Netmiko 3.x
            if delay_factor is None:
                tmp_delay_factor = self.global_delay_factor
            else:
                tmp_delay_factor = self.select_delay_factor(delay_factor)
            compat_timeout = calc_old_timeout(
                max_loops=max_loops,
                delay_factor=tmp_delay_factor,
                loop_delay=0.2,
                old_timeout=self.timeout,
            )
            msg = f"""\n
        You have chosen to use Netmiko's delay_factor compatibility mode for
        send_command. This will revert Netmiko to behave similarly to how it
        did in Netmiko 3.x (i.e. to use delay_factor/global_delay_factor and
        max_loops).

        Using these parameters Netmiko has calculated an effective read_timeout
        of {compat_timeout} and will set the read_timeout to this value.

        Please convert your code to that new format i.e.:

            net_connect.send_command(cmd, read_timeout={compat_timeout})

        And then disable delay_factor_compat.

        delay_factor_compat will be removed in Netmiko 5.x.\n"""
            warnings.warn(msg, DeprecationWarning)

            # Override the read_timeout with Netmiko 3.x way :-(
            read_timeout = compat_timeout

        else:
            # No need for two deprecation messages so only display this if not using
            # delay_factor_compat
            if delay_factor is not None or max_loops is not None:
                msg = """\n
        Netmiko 4.x has deprecated the use of delay_factor/max_loops with
        send_command. You should convert all uses of delay_factor and max_loops
        over to read_timeout=x where x is the total number of seconds to wait
        before timing out.\n"""
                warnings.warn(msg, DeprecationWarning)

        start_time = time.time()
        while time.time() - start_time < read_timeout:
            output = self.find_prompt()

            log.debug("Check if we are already on BMC prompt")
            if re.search(prompt_pattern, output):
                log.debug("On BMC Prompt")
                return

            log.debug("Check if BMC Username Prompt detected")
            if re.search(username_pattern, output):
                log.debug(f"BMC Username pattern detected, sending Username={bmc_username}")
                time.sleep(1)
                self.write_channel(bmc_username)
                time.sleep(1 * delay_factor)
                output = self.find_prompt()

            log.debug("Check if BMC Password Prompt detected")
            if re.search(pwd_pattern, output):
                log.debug(f"BMC Password pattern detected, sending Password={bmc_pass}")
                self.write_channel(bmc_pass)
                time.sleep(.5 * delay_factor)
                output = self.find_prompt()

                if re.search(prompt_pattern, output):
                    log.debug("On BMC Prompt")
                    return

                if re.search(pwd_pattern, output):
                    self.write_channel(bmc_pass)
                    time.sleep(.5 * delay_factor)

        # Last try to see if we already logged in
        self.write_channel(self.TELNET_RETURN)
        time.sleep(.5 * delay_factor)
        output = self.find_prompt()
        if re.search(prompt_pattern, output):
            log.debug("On BMC Prompt")
            return

        raise NetMikoAuthenticationException("LAST_TRY login failed for BMC Prompt")

    def set_base_prompt(self, pri_prompt_terminator='#', alt_prompt_terminator='$', delay_factor=1,
                        pattern: Optional[str] = None):
        """Sets self.base_prompt

        Used as delimiter for stripping of trailing prompt in output.

        Should be set to something that is general and applies in multiple contexts. For Cisco
        devices this will be set to router hostname (i.e. prompt without '>' or '#').

        This will be set on entering user exec or privileged exec on Cisco, but not when
        entering/exiting config mode.

        :param pri_prompt_terminator: Primary trailing delimiter for identifying a device prompt
        :type pri_prompt_terminator: str

        :param alt_prompt_terminator: Alternate trailing delimiter for identifying a device prompt
        :type alt_prompt_terminator: str

        :param delay_factor: See __init__: global_delay_factor
        :type delay_factor: int

        :param pattern: Regular expression pattern to search for in find_prompt() call
        :type pattern: str
        """
        return super().set_base_prompt(pri_prompt_terminator=pri_prompt_terminator,
                                       alt_prompt_terminator=alt_prompt_terminator,
                                       delay_factor=delay_factor,
                                       pattern=pattern)

    def disable_paging(self, *args, **kwargs):
        """Paging is disabled by default."""
        return ""


class CiscoBspSSH(CiscoBsp):
    """
    CiscoBspSSH is based of CiscoBsp -- CiscoBaseConnection
    """

    pass


class CiscoBspTelnet(CiscoBsp):
    """
    CiscoBspTelnet is based of CiscoBsp -- CiscoBaseConnection
    """

    def telnet_login(self, pri_prompt_terminator=r']\s*\#', alt_prompt_terminator=r']\s*\$', username_pattern=r'login',
                     pwd_pattern=r'assword', delay_factor=1, max_loops=20, read_timeout=10.0):
        """
        Telnet login to BSP prompt

        :param pri_prompt_terminator: primary prompt pattern (for root user)
        :param alt_prompt_terminator: alternate prompt pattern (for non-root user eg: cisco user)
        :param username_pattern: username prompt pattern
        :param pwd_pattern: password prompt pattern
        :param delay_factor: Factor to adjust delays
        :param max_loops: max number of iterations for attempting to login to BSP prompt before raising exception
        :param read_timeout: maximum time to wait looking for pattern
        :return:
        """

        self.TELNET_RETURN = '\n'
        delay_factor = self.select_delay_factor(delay_factor)
        my_username = self.username
        my_password = self.password
        return_msg = ''

        if self.delay_factor_compat:
            # For compatibility calculate the old equivalent read_timeout
            # i.e. what it would have been in Netmiko 3.x
            if delay_factor is None:
                tmp_delay_factor = self.global_delay_factor
            else:
                tmp_delay_factor = self.select_delay_factor(delay_factor)
            compat_timeout = calc_old_timeout(
                max_loops=max_loops,
                delay_factor=tmp_delay_factor,
                loop_delay=0.2,
                old_timeout=self.timeout,
            )
            msg = f"""\n
        You have chosen to use Netmiko's delay_factor compatibility mode for
        send_command. This will revert Netmiko to behave similarly to how it
        did in Netmiko 3.x (i.e. to use delay_factor/global_delay_factor and
        max_loops).

        Using these parameters Netmiko has calculated an effective read_timeout
        of {compat_timeout} and will set the read_timeout to this value.

        Please convert your code to that new format i.e.:

            net_connect.send_command(cmd, read_timeout={compat_timeout})

        And then disable delay_factor_compat.

        delay_factor_compat will be removed in Netmiko 5.x.\n"""
            warnings.warn(msg, DeprecationWarning)

            # Override the read_timeout with Netmiko 3.x way :-(
            read_timeout = compat_timeout

        else:
            # No need for two deprecation messages so only display this if not using
            # delay_factor_compat
            if delay_factor is not None or max_loops is not None:
                msg = """\n
        Netmiko 4.x has deprecated the use of delay_factor/max_loops with
        send_command. You should convert all uses of delay_factor and max_loops
        over to read_timeout=x where x is the total number of seconds to wait
        before timing out.\n"""
                warnings.warn(msg, DeprecationWarning)

        start_time = time.time()
        while time.time() - start_time < read_timeout:
            try:
                # self.read_channel which internally calls telnetlib.read_ver_eager() returns empty string
                log.debug("Reading channel for the first time")
                output = self.read_channel()

                # self.find_prompt will return prompt after logging in
                log.debug(f"Output after reading channel for first time: {output}")
                if output == '':
                    log.debug("output is empty, doing find_prompt()")
                    output = self.find_prompt()
                    log.debug(f"Output after doing find_prompt: {output}")
                    return_msg += output

                log.debug("Checking if Password Prompt")
                if re.search(pwd_pattern, output):
                    log.debug("Differentiate whether it is password prompt for BMC or BSP")
                    self.write_channel(self.TELNET_RETURN)
                    output = self.find_prompt()
                    return_msg += output

                log.debug("Checking if BMC prompt")
                if 'bmc' in output:
                    log.debug("BMC Login prompt detected")
                    self.bmc_login()
                    self.bmc_to_bsp_prompt()
                    output = self.find_prompt()
                    return_msg += output

                log.debug("Searching for username pattern")
                if re.search(username_pattern, output):
                    log.debug(f"Username pattern detected, sending Username={my_username}")
                    time.sleep(1)
                    self.write_channel(my_username + self.TELNET_RETURN)
                    output = self.read_channel()
                    return_msg += output
                    log.debug(f"After sending username, the output pattern is={output}")

                log.debug("Searching for password pattern")
                if re.search(pwd_pattern, output):
                    self.write_channel(my_password + self.TELNET_RETURN)
                    output = self.read_channel()
                    return_msg += output

                    if re.search(pri_prompt_terminator, output, flags=re.M) or re.search(alt_prompt_terminator, output,
                                                                                         flags=re.M):
                        return return_msg

                    if re.search(pwd_pattern, output):
                        self.write_channel(my_password + self.TELNET_RETURN)
                        output = self.read_channel()
                        return_msg += output

                # Check for device with no password configured
                if re.search(r"assword required, but none set", output):
                    raise NetMikoAuthenticationException(
                        f"Telnet login failed - Password required, but none set: {self.host}")

                # Check if already on BSP prompt
                if re.findall(pri_prompt_terminator, output) or re.findall(alt_prompt_terminator, output):
                    return return_msg

                self.write_channel(self.TELNET_RETURN)
            except EOFError:
                raise NetMikoAuthenticationException(f"EOFError Telnet login failed: {self.host}")

        # Last try to see if we already logged in
        self.write_channel(self.TELNET_RETURN)
        time.sleep(5)
        output = self.read_channel()
        return_msg += output
        if (re.search(pri_prompt_terminator, output, flags=re.M) or re.search(alt_prompt_terminator, output,
                                                                              flags=re.M)):
            return return_msg

        raise NetMikoAuthenticationException(f"LAST_TRY Telnet login failed: {self.host}")
