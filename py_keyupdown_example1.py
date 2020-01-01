import signal
from PyKeyUpKeyDown import PyKeyUpKeyDown

done = False

def on_key_event(e):
  print("Observed %s for keycode=%u mappedkey=%s" % ("keyup" if e['is_up'] else "Keydown", e['keycode'], e['key']))

def cleanup(signum, frame):
  global done
  print("Caught signal %s. Shutting down." % (str(signum)))
  done = True

signal.signal(signal.SIGINT, cleanup)

key_listener = PyKeyUpKeyDown(debug=False) #  Set the debug flag to true to see more info.
rtn = key_listener.setup_keylisten()
if rtn:
  print("Successfully set up keylistener.  Press Ctrl+c to exit.")
  while not done:
    e = key_listener.get_next_key_event()
    on_key_event(e)
else:
  print("Was unable to set up keylistener.  Perhaps you need to use 'sudo'?")


key_listener.cleanup()
