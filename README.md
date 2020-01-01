#  Purpose

The purpose of this repository is to provide a demo solution to the problem of remotely controlling a Raspberry Pi controlled robot in real-time over a WiFi network from a Linux terminal environment.

#  How To Use

Before you begin using this application, you will need to adjust the following to suit your environment:

-  You'll need to set the correct GPIO pin numbers to match your physical wiring.
-  You'll also need to adjust the port and ip address of the server which is included in robot_tank_client.py to match where you plan to run the server.
-  Also, you should make sure that the server port matches that the client will try to connect to.
-  Make sure the client and server are both running on computers that are on the same LAN.  If you want this to work over the internet, you'll need to take special steps to route ports through your router, or use a tuennel.

This server application can be launched on the computer where you plan to control the robot using this command:

```
sudo python3 robot_tank_server.py
```

'sudo' is necessary because root access is necessary for obtaining keyboard events in a terminal environment.

In order to launch the client on the Raspbrry Pi that controlls the robot, use this command:

```
python3 robot_tank_client.py
```

You should now be able to control the robot remotely using the keyboard over the network.
