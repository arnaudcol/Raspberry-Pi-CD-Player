================================================================================
RASPBERRY PI 4 CD PLAYER SETUP - PYGAME + VLC + PULSEAUDIO AT BOOT
================================================================================
Hardware: Raspberry Pi 4 with NanoSound One
OS:       Raspberry Pi OS Lite (no desktop, multi-user.target)
Display:  HDMI via pygame 1.9.6 (fbcon framebuffer driver)
Audio:    VLC + PulseAudio/ALSA
Date:     April 2026
================================================================================


--------------------------------------------------------------------------------
PROBLEM SUMMARY
--------------------------------------------------------------------------------
Running a pygame + VLC python script at boot via systemd failed because:
  1. pygame could not open a display (no controlling TTY)
  2. getty@tty1 was holding /dev/tty1, blocking fbcon access
  3. A user service lacks the session context needed for TTY/framebuffer access

Solution: Use a system-level systemd service that owns /dev/tty1 directly,
and mask getty@tty1 so nothing else holds the console.


--------------------------------------------------------------------------------
STEP 1 - DISABLE GETTY ON TTY1
--------------------------------------------------------------------------------
getty is the login prompt that holds /dev/tty1 at boot. It must be masked
so your script can take exclusive control of the framebuffer.

  sudo systemctl stop getty@tty1
  sudo systemctl disable getty@tty1
  sudo systemctl mask getty@tty1


--------------------------------------------------------------------------------
STEP 2 - PYTHON SCRIPT ENVIRONMENT (top of cdplayer12.py)
--------------------------------------------------------------------------------
These lines must appear at the very top of your script, before any other
imports, especially before 'import pygame'.

  import os
  import sys

  os.environ['SDL_VIDEODRIVER'] = 'fbcon'
  os.environ['SDL_FBDEV'] = '/dev/fb0'
  os.environ['SDL_NOMOUSE'] = '1'
  os.environ['HOME'] = '/home/pi'
  os.environ['XDG_RUNTIME_DIR'] = '/run/user/1000'
  os.environ['PULSE_RUNTIME_PATH'] = '/run/user/1000/pulse'

  import pygame


--------------------------------------------------------------------------------
STEP 3 - SYSTEMD SERVICE FILE
--------------------------------------------------------------------------------
Create the service file:

  sudo nano /etc/systemd/system/cdplayer.service

Contents:

  [Unit]
  Description=CD Player
  After=local-fs.target sound.target
  Wants=sound.target

  [Service]
  Type=simple
  User=pi
  Group=pi
  TTYPath=/dev/tty1
  StandardInput=tty
  StandardOutput=tty
  StandardError=journal
  #TTYReset=yes
  #TTYVHangup=yes
  #TTYVTDisallocate=yes

  #ExecStart=/usr/bin/python3 /home/pi/cdplayer12.py
  ExecStart=/bin/bash -c '/usr/bin/python3 /home/pi/cdplayer12.py >> /home/pi/cdplayer.log 2>&1'

  Restart=on-failure
  RestartSec=5

  Environment=SDL_VIDEODRIVER=fbcon
  Environment=SDL_FBDEV=/dev/fb0
  Environment=SDL_NOMOUSE=1
  Environment=SDL_AUDIODRIVER=alsa
  Environment=HOME=/home/pi
  Environment=XDG_RUNTIME_DIR=/run/user/1000
  Environment=PULSE_RUNTIME_PATH=/run/user/1000/pulse

  [Install]
  WantedBy=multi-user.target

Key service options explained:
  TTYPath=/dev/tty1          - assigns /dev/tty1 to this service
  StandardInput=tty          - gives the process a real controlling terminal
  TTYReset=yes               - resets TTY state on service stop
  TTYVHangup=yes             - hangs up TTY on service stop
  TTYVTDisallocate=yes       - releases virtual terminal on service stop
  SDL_AUDIODRIVER=alsa       - bypasses PulseAudio for SDL, uses ALSA directly


--------------------------------------------------------------------------------
STEP 4 - ENABLE AND START THE SERVICE
--------------------------------------------------------------------------------
  sudo systemctl daemon-reload
  sudo systemctl enable cdplayer
  sudo systemctl start cdplayer


--------------------------------------------------------------------------------
STEP 5 - VERIFY IT IS RUNNING
--------------------------------------------------------------------------------
  sudo systemctl status cdplayer
  sudo journalctl -u cdplayer -f


--------------------------------------------------------------------------------
STEP 6 - MANUAL DEBUG (if needed)
--------------------------------------------------------------------------------
Run the script manually as the pi user with the same environment as the service:

  sudo -u pi SDL_VIDEODRIVER=fbcon SDL_FBDEV=/dev/fb0 python3 /home/pi/cdplayer12.py


--------------------------------------------------------------------------------
NOTES
--------------------------------------------------------------------------------
- pi user groups required: video, tty (pi was already in both by default)
- No group changes to pi were necessary in this setup
- User ID 1000 is the default for the pi user; verify with: id -u pi
- If you rename your script, update ExecStart in the service file accordingly
- To check if another process is holding tty1:
    systemctl status getty@tty1
- To unmask getty in future if needed:
    sudo systemctl unmask getty@tty1

================================================================================
END OF DOCUMENT
================================================================================


Note groups that make this work?
pi : pi adm tty dialout cdrom sudo audio video plugdev games users input render netdev spi i2c gpio

if you need to use the pi normally again
enable tty1 and disable cdplayer
