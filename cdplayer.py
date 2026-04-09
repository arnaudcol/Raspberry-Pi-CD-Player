#!/usr/bin/python3
import pygame, vlc, sys, os, time, discid, musicbrainzngs, io, evdev, pycdio, cdio, threading, logging
import RPi.GPIO as GPIO
from pygame.locals import *
from PIL import Image

# Shared stop event for clean thread shutdown
stop_event = threading.Event()

logging.basicConfig(
    filename='cdplayer.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w' # 'a' for append (default), 'w' for overwrite
)

logging.warning("This is a warning message.")
logging.error("This is an error message.")
logging.info("This is an info message.")

# Also redirect stdout and stderr to the log file
#log_file = open('/home/pi/cdplayer.log', 'a')
#sys.stdout = log_file
#sys.stderr = log_file

#Setting for accessing data from Music Brains
musicbrainzngs.set_useragent("python-discid-example", "0.1", "yosur@mail")

#Setup the display
#os.putenv('SDL_FBDEV', '/dev/fb0') 
os.environ['SDL_VIDEODRIVER'] = 'fbcon'
os.environ['SDL_FBDEV'] = '/dev/fb0'

#Setup the remote control
GPIO.setmode(GPIO.BOARD)  # Numbers GPIOs by physical location
GPIO.setup(11, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
def binary_aquire(pin, duration):
    # aquires data as quickly as possible
    t0 = time.time()
    results = []
    while (time.time() - t0) < duration:
        results.append(GPIO.input(pin))
    return results
def on_ir_receive(pinNo, bouncetime=150):
    # when edge detect is called (which requires less CPU than constant
    # data acquisition), we acquire data as quickly as possible
    data = binary_aquire(pinNo, bouncetime/1000.0)
    if len(data) < bouncetime:
        return
    rate = len(data) / (bouncetime / 1000.0)
    pulses = []
    i_break = 0
    # detect run lengths using the acquisition rate to turn the times in to microseconds
    for i in range(1, len(data)):
        if (data[i] != data[i-1]) or (i == len(data)-1):
            pulses.append((data[i-1], int((i-i_break)/rate*1e6)))
            i_break = i
    # decode ( < 1 ms "1" pulse is a 1, > 1 ms "1" pulse is a 1, longer than 2 ms pulse is something else)
    # does not decode channel, which may be a piece of the information after the long 1 pulse in the middle
    outbin = ""
    for val, us in pulses:
        if val != 1:
            continue
        if outbin and us > 2000:
            break
        elif us < 1000:
            outbin += "0"
        elif 1000 < us < 2000:
            outbin += "1"
    try:
        return int(outbin, 2)
    except ValueError:
        # probably an empty code
        return None
def destroy():
    GPIO.cleanup()

#Setup the touchscreen
touchscreen = "wch.cn USB2IIC_CTP_CONTROL"
devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
for device in devices:
        #print(device.path, device.name, device.phys)
        if device.name==touchscreen:
                #print(device.path, device.name, device.phys)
            touch = evdev.InputDevice(device.path)

#Initialize pygame
#pygame.init()

#Initilize the display
pygame.display.init()
screen = pygame.display.set_mode([1920,1080], pygame.FULLSCREEN)
pygame.mouse.set_visible(False)

#Load font settings
pygame.font.init()
font_title = pygame.font.SysFont(None,75)
font_volume = pygame.font.SysFont(None,125)
font_track = pygame.font.SysFont(None,100)

#path to images
picdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'images')

#Setup the CD-Rom
cd_rom = cdio.Device(driver_id=pycdio.DRIVER_UNKNOWN)
cd_current_disc = 0                                                 #current disc information
cd_current_track = 1                                                #Current track number
cd_total_tracks = 0                                                 #Total number of tracks
cd_track_list = []                                                  #Track list
cd_front_cover = "cd.png"                                           #cd_front_cover image
cd_tracks = {}
cd_restart = False

#Setup VLC
vlc_player = vlc.MediaPlayer("cdda:///dev/sr0", (":cdda-track=1")) # Replace /dev/sr0 with your CD drive path
vlc_player.audio_output_set('pulse')
vlc_volume = 25                                                     #Volume level

def load_interface():
    screen.fill((0,0,0))

    #Default CD image
    pygameSurface = pygame.image.load(os.path.join(picdir,"cd.png")).convert_alpha()
    pygameSurface = pygame.transform.scale(pygameSurface, (600,600))
    #screen.blit(pygameSurface, (1320,200))
    screen.blit(pygameSurface, (0,200))

    #Next Image
    img = pygame.image.load(os.path.join(picdir,"next_white.png")).convert_alpha()
    img = pygame.transform.scale(img, (180,180))
    screen.blit(img, (1740,900))

    #Previous Image
    img = pygame.image.load(os.path.join(picdir,"previous_white.png")).convert_alpha()
    img = pygame.transform.scale(img, (180,180))
    screen.blit(img, (0,900))

    #Play Pause Image
    img = pygame.image.load(os.path.join(picdir,"play_pause_white.png")).convert_alpha()
    img = pygame.transform.scale(img, (220,220))
    screen.blit(img, (850,890))

    #Power Image
    img = pygame.image.load(os.path.join(picdir,"power_white.png")).convert_alpha()
    img = pygame.transform.scale(img, (125,125))
    screen.blit(img, (20,20))

    #Volume Up
    img = pygame.image.load(os.path.join(picdir,"audio-add-xxl.png")).convert_alpha()
    img = pygame.transform.scale(img, (125,125))
    screen.blit(img, (1740,0))

    #Volume Down
    img = pygame.image.load(os.path.join(picdir,"audio-remove-xxl.png")).convert_alpha()
    img = pygame.transform.scale(img, (125,125))
    screen.blit(img, (1300,0))

    #Artist Image
    img = pygame.image.load(os.path.join(picdir,"artist_white.png")).convert_alpha()
    img = pygame.transform.scale(img, (100,100))
    screen.blit(img, (630,350))

    #Album Image
    img = pygame.image.load(os.path.join(picdir,"cd_white.png")).convert_alpha()
    img = pygame.transform.scale(img, (100,100))
    screen.blit(img, (630,550))

    #Time Image
    img = pygame.image.load(os.path.join(picdir,"time_white.png")).convert_alpha()
    img = pygame.transform.scale(img, (100,100))
    screen.blit(img, (630,750))

    pygame.display.flip()

def show_track_text(text,blink):
    show_cover()
    pygame.draw.rect(screen, (0,0,0), (625,200,1920,100))
    if(blink):
        pygame.display.flip()
        time.sleep(1)
    if(isinstance(text,(int,float))):
        screen.blit(font_track.render(str(cd_current_track) + "/" + str(cd_total_tracks) + " " + cd_track_list[int(cd_current_track)-1], False, (255, 255, 255)),(630, 200))
        logging.info("Showing Track: " + str(cd_current_track) + "/" + str(cd_total_tracks) + " " + cd_track_list[int(cd_current_track)-1])
    else:
        screen.blit(font_track.render(text, False, (255, 255, 255)),(630, 200))
        logging.info("Showing Text: " + text)
    pygame.display.flip()

def show_cover():
    pygameSurface = pygame.image.load(os.path.join(picdir,cd_front_cover)).convert_alpha()
    pygameSurface = pygame.transform.scale(pygameSurface, (600,600))
    #screen.blit(pygameSurface, (1320,200))
    screen.blit(pygameSurface, (0,200))
    pygame.display.flip()
    logging.info("Showing Front Cover: " + cd_front_cover)

def change_volume():
    pygame.draw.rect(screen, (0,0,0), (1450,0,250,125))
    screen.blit(font_volume.render(str(vlc_volume) + "%", False, (255, 255, 255)),(1500, 20))
    pygame.display.flip()
    vlc_player.audio_set_volume(vlc_volume)
    logging.info("New Volume: " + str(vlc_volume))

def load_cd():
    show_track_text("Loading Disc",False)
    logging.info("Loading Disc")
    global cd_current_disc, cd_total_tracks, cd_track_list, cd_tracks
    cd_current_disc = discid.read()
    cd_current_track = 1
    cd_total_tracks = cd_current_disc.last_track_num
    cd_track_list = []
    cd_tracks = {}
    play_track(cd_current_track)
    change_volume()
    load_cd_info()

def load_cd_info():
    global cd_track_list, cd_front_cover,cd_tracks
    show_track_text("Getting Track Listing", False)
    try:
        result = musicbrainzngs.get_releases_by_discid(cd_current_disc.id,includes=["artists","recordings"])
    except musicbrainzngs.ResponseError:
        show_track_text("Disc not found or bad response", True)
    else:
        if result.get("disc"):
            cd_info = result["disc"]["release-list"][0]
            for x in cd_info['medium-list']:
                for y in x['disc-list']:
                    if(y['id'] == cd_current_disc.id):
                        logging.info("Found Disc: " + str(cd_info["title"]))
                        x['track-list']
                        for z in x['track-list']:
                            cd_track_list.append(z['recording']['title'])
                            cd_tracks[z['position']]={'artist':z['artist-credit-phrase'],'title':z['recording']['title'],'length':z['length'],'minutes':int((int(z['length']) / (1000 * 60)) % 60),'seconds':int(int(z['length'])/1000%60)}
                            logging.info("Track: " + str(z['recording']['title']))
            if cd_info["artist-credit-phrase"] == 'Various Artists':
                screen.blit(font_title.render(str(cd_info["artist-credit-phrase"] + ": " + str(cd_tracks['1']['artist']) ), False, (255, 255, 255)),(750, 380)) #Need to expand this to other tracks
            else:
                screen.blit(font_title.render(str(cd_info["artist-credit-phrase"]), False, (255, 255, 255)),(750, 380))
            screen.blit(font_title.render(str(cd_info["title"]), False, (255, 255, 255)),(750, 580))
            screen.blit(font_title.render(str(cd_tracks['1']['minutes']) + ":" + str(cd_tracks['1']['seconds']), False, (255, 255, 255)),(750, 780))
            pygame.draw.rect(screen, (0,0,0), (625,200,1920,100))
            pygame.display.flip()
            show_track_text(cd_current_track, False)
            try:
                cover_art_b = musicbrainzngs.get_image_front(result["disc"]["release-list"][0]["id"],size=250)
            except musicbrainzngs.ResponseError:
                cd_front_cover = "cd.png"
            except musicbrainzngs.WebServiceError:
                cd_front_cover = "cd.png"
            else:
                image = Image.open(io.BytesIO(cover_art_b))
                image.save(os.path.join(picdir,"cover.png"))
                cd_front_cover = "cover.png"
            show_cover()
        elif result.get("cdstub"):
            print("artist:\t" % result["cdstub"]["artist"])
            print("title:\t" % result["cdstub"]["title"])

#vlc event manager requires an event to be sent to the calling function!!!
def play_track(track):
    global vlc_player, cd_restart
    cd_restart = False
    vlc_player = vlc.MediaPlayer("cdda:///dev/sr0", (":cdda-track=" + str(track)))
    vlc_player.audio_set_volume(vlc_volume)
    vlc_player.play()
    logging.info("Playing: "+ str(track) + " @ Volume: " + str(vlc_volume))
    if(len(cd_track_list) != 0):
        show_track_text(track, False)

#Threads
def play_cd():
    global vlc_player, cd_current_track, cd_restart
    while not stop_event.is_set():
        vlc_state = vlc_player.get_state()
        logging.info(vlc_state)
        logging.info(cd_restart)
        if vlc_state == vlc.State.NothingSpecial or cd_restart:
            try:
                if len(cd_rom.get_disc_mode()) > 0:
                    load_cd()
                    time.sleep(5)
            except:
                logging.info("No CD : VLC NothingSpecial")
                load_interface()
                show_track_text("Insert Disc", False)
                show_cover()
        elif vlc_state == vlc.State.Ended:
            cd_current_track += 1
            if cd_current_track > cd_total_tracks:
                #cd_current_track = cd_total_tracks
                vlc_player.pause()
            else:
                vlc_player.pause()
                play_track(cd_current_track)
        elif vlc_state == vlc.State.Stopped:
            pass
            #vlc_player.stop()
            #cd_restart = True
        elif vlc_state == vlc.State.Paused:
            show_track_text(cd_current_track, True)
        else:
            pass
        stop_event.wait(1)

def touch_control():
    global cd_current_track, vlc_volume
    for event in touch.read_loop():                 # Loop over all events
        if event.type == evdev.ecodes.EV_ABS:       # Check if the event is a touch event
            if(event.code == 53):
                x = event.value
            if(event.code == 54):
                y = event.value
        elif event.type == evdev.ecodes.EV_KEY:
            if(event.value == 0):                   #This is triggered on release
                if x < 500 and y < 500:
                    shutdown()
                elif x < 400 and y > 3300:                  #Previous Track
                    cd_current_track -= 1
                    if cd_current_track <= 1:
                        cd_current_track = 1
                    else:
                        pass
                    play_track(cd_current_track)
                elif x > 1650 and x < 2500 and y > 3300:    #Play/Pause
                    vlc_player.pause()
                elif x > 3500 and y > 3300:                 #Next Track
                    cd_current_track += 1
                    if cd_current_track > cd_total_tracks:
                        cd_current_track = cd_total_tracks
                    else:
                        pass
                    play_track(cd_current_track,)
                elif x > 3500 and y < 500:                  #Volume Up
                    vlc_volume += 5
                    change_volume()
                elif x > 2750 and x < 3000 and y < 500:     #Volume Down
                    vlc_volume -= 5
                    change_volume()

def remote_control():
    global cd_current_track, vlc_volume, cd_front_cover, cd_restart
    while not stop_event.is_set():
        GPIO.wait_for_edge(11, GPIO.FALLING)
        code = on_ir_receive(11)
        if code == 16726470:                        #Power
            shutdown()
        elif code == 16733100:                      #Arrow Up
            pass
        elif code == 16731060:                      #Arrow Down
            pass
        elif code == 16750950:                      #Arrow Left
            cd_current_track -= 1
            if cd_current_track <= 1:
                cd_current_track = 1
            else:
                pass
            vlc_player.pause()
            play_track(cd_current_track)
        elif code == 16745340:                      #Arrow Right
            cd_current_track += 1
            if cd_current_track > cd_total_tracks:
                cd_current_track = cd_total_tracks
            else:
                pass
            vlc_player.pause()
            play_track(cd_current_track)
        elif code == 16741260:                      #Select
            logging.info(vlc_player.get_state())
            current_state = vlc_player.get_state()
            if  current_state == vlc.State.NothingSpecial or current_state == vlc.State.Stopped:
                play_track(cd_current_track)
            elif current_state == vlc.State.Playing or current_state == vlc.State.Paused:
                vlc_player.pause()
        elif code == 16759110:                      #Menu
            pass
        elif code == 16765740:                      #Home
            vlc_player.stop()
            cd_front_cover = "cd.png"
            cd_restart = True
            cd_rom.eject_media_drive() #just eject_media doesn't work it won't load disc after eject
        elif code == 16714230:                      #Return
            pass
        elif code == 16712190:                      #Volume Up
            vlc_volume += 5
            change_volume()
        elif code == 16744830:                      #Volume Down
            vlc_volume -= 5
            change_volume()

def shutdown():
    logging.info("Shutdown initiated")
    stop_event.set()                        # Signal all threads to stop
    vlc_player.stop()                       # Stop VLC playback
    cd_load.join(timeout=3)                 # Wait for cd thread to finish
    remote_load.join(timeout=3)             # Wait for remote thread to finish
    touch_load.join(timeout=3)              # Wait for touch thread to finish
    GPIO.cleanup()                          # Clean up GPIO
    pygame.quit()                           # Quit pygame
    logging.info("Shutdown complete")
    sys.exit(0)

if __name__ =="__main__":
    load_interface()

    cd_load = threading.Thread(target=play_cd, daemon=True)
    remote_load = threading.Thread(target=remote_control, daemon=True)
    touch_load = threading.Thread(target=touch_control, daemon=True)

    remote_load.start()
    touch_load.start()
    cd_load.start()

    try:
        while not stop_event.is_set():
            stop_event.wait(1)
    except KeyboardInterrupt:
        shutdown()