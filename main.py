# Tkinter modules
from tkinter import *
from toast_message import show_toast

# Arduino modules
import serial 
import serial.tools.list_ports
from serial import Serial

# Importing constants
from values import (ARDUINO_PORT, BAUD_RATE, WINDOW_SIZE, WINDOW_LOCATION,
                    MOUSE_ACCELERATION, MOUSE_STOP_THRESHOLD_TIME,
                    MOUSE_INITIAL_SPEED, MOUSE_MAX_SPEED, DEVICE_DESC,
                    THRESHOLD_TIME, TYPING_THRESHOLD_TIME, CLICK_THRESHOLD_TIME)
from colors import color
from controls import actions, combine_actions

# Modules to control keyboard and mouse
from pynput.mouse import Button as MouseButton, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyController

from threading import Thread
from time import sleep
from time import time
import pickle

import argparse

parser = argparse.ArgumentParser(description='Starter script to run the IR signal detection process.')
parser.add_argument('--no_ui', action='store_true', help='Flag to decide whether we should render a UI or not.')
args = parser.parse_args()

# arduino microcontroller object
arduino = None

# Application configuration
windowSize = WINDOW_SIZE
windowLocation = WINDOW_LOCATION
windowTitle = "IR +"
window = Tk()

autoStartFlag = False

def exitApplication():
    global isReceiverRunning
    isReceiverRunning = False
    window.destroy()
    exit()

if args.no_ui:
    # Hide the main tkinter window
    print('Running in hidden mode.')
    autoStartFlag = True
    window.withdraw()

ports = serial.tools.list_ports.comports()
for port, desc, hwid in sorted(ports):
    if DEVICE_DESC in desc:
        print(f"{port}")
        arduino = Serial(port, BAUD_RATE, timeout=0.1)

if arduino is None:
    print("Arduino not connected")
    show_toast(window, 'Arduino not connected', on_close=exitApplication)


# Pynput configuration
mouse = MouseController()
keyboard = KeyController()

commandOptions = combine_actions(actions.values())
isReceiverRunning = False
performActionFlag = None
toggleBtnText = None
commandBoxText = None
messageLabelText = None
decodedSignal = ''
configMap = {}
lastAction = ''
lastActionTime = 0
thresholdTime = THRESHOLD_TIME
typingThresholdTime = TYPING_THRESHOLD_TIME
clickThresholdTime = CLICK_THRESHOLD_TIME
typingIndex = 0
actionMode = None
availableModes = []

mouseAcceleration = MOUSE_ACCELERATION
mouseStopThresholdTime = MOUSE_STOP_THRESHOLD_TIME
mouseInitialSpeed = MOUSE_INITIAL_SPEED
mouseMaxSpeed = MOUSE_MAX_SPEED
mouseSpeed = 0

PICKLE_FILE_PATH = 'data.pkl'


def resetConfiguration():
    global configMap, messageLabelText
    configMap = {}
    with open(PICKLE_FILE_PATH, 'wb') as handle:
        pickle.dump(configMap, handle, protocol=pickle.HIGHEST_PROTOCOL)
    messageLabelText.set('Saved configurations cleared !')

def saveCommand():
    global configMap, availableModes
    if decodedSignal == '':
        return
    action = commandBoxText.get()
    if decodedSignal in configMap:
        # We already have some action saved for this signal.
        previous_action = configMap[decodedSignal]
        if isinstance(previous_action, list):
            configMap[decodedSignal] = [action, *previous_action]
        else:
            configMap[decodedSignal] = [action, previous_action]
    else:
        configMap[decodedSignal] = action

    print(decodedSignal, ' => ', configMap[decodedSignal])

    # Save the config data in pickle file.
    with open(PICKLE_FILE_PATH, 'wb') as handle:
        pickle.dump(configMap, handle, protocol=pickle.HIGHEST_PROTOCOL)

    # Update the list of available modes.
    availableModes = getAvailableModes()

    messageLabelText.set('Saved !')
    show_toast(window, 'Saved!')

def getAvailableModes():
    global configMap
    used_actions = combine_actions([
        action
        if isinstance(action, list)
        else [action]
        for action in configMap.values()
    ])
    modes = list(filter(
        lambda mode: set(actions[mode]) & set(used_actions),
        actions.keys()
    ))

    ignore_mode = 'App commands'
    if ignore_mode in modes:
        modes.remove(ignore_mode)

    return modes

def startIRThread():
    global availableModes, isReceiverRunning, toggleBtnText

    # Update the list of available modes.
    availableModes = getAvailableModes()
    print(availableModes)

    isReceiverRunning = True
    toggleBtnText.set('Stop')
    IR_Thread = Thread(target=startDetection)
    IR_Thread.start()

def stopIRThread():
    global isReceiverRunning, toggleBtnText
    isReceiverRunning = False
    toggleBtnText.set('Start')

def toggleIRThread():
    global isReceiverRunning
    if isReceiverRunning:
        stopIRThread()
    else:
        startIRThread()
        window.after(0, lambda: show_toast(window, 'Starting remote control'))


def startDetection():
    global decodedSignal, messageLabelText
    while isReceiverRunning:
        try:
            data = arduino.readline()[:-2]
            if data:
                try:
                    # IR signal received 
                    data = data.decode('utf-8')
                    decodedSignal = data
                    # messageLabelText.set('<' + decodedSignal + '>' + ' = ' + str(len(decodedSignal)))
                    messageLabelText.set('<' + decodedSignal + '>')
                    if performActionFlag.get() == 1:
                        if decodedSignal in configMap:
                            performAction(configMap[decodedSignal])
                except Exception as e:
                    print(e)
        except:
            continue

def performTyping(action):
    global typingIndex
    key = action[-1]
    typingMap = {
        '0': ['0'],
        '1': ['1'],
        '2': ['a', 'b', 'c', '2'],
        '3': ['d', 'e', 'f', '3'],
        '4': ['g', 'h', 'i', '4'],
        '5': ['j', 'k', 'l', '5'],
        '6': ['m', 'n', 'o', '6'],
        '7': ['p', 'q', 'r', 's', '7'],
        '8': ['t', 'u', 'v', '8'],
        '9': ['w', 'x', 'y', 'z', '9']
    }
    if key not in typingMap:
        return
    
    currentTime = int(round(time() * 1000))

    if lastAction != action:
        # New key is typed
        typingIndex = 0
        keyboard.press(typingMap[key][typingIndex])
        keyboard.release(typingMap[key][typingIndex])
    else:
        # Same key is typed
        if currentTime - lastActionTime > thresholdTime:
            # Repeat this key
            typingIndex = 0
            keyboard.press(typingMap[key][typingIndex])
            keyboard.release(typingMap[key][typingIndex])
        elif currentTime - lastActionTime > typingThresholdTime:
            # Change to next index
            typingIndex = (typingIndex + 1) % (len(typingMap[key]))
            keyboard.press(Key.backspace)
            keyboard.release(Key.backspace)
            keyboard.press(typingMap[key][typingIndex])
            keyboard.release(typingMap[key][typingIndex])
    

def performAction(action):
    global lastAction, lastActionTime, mouseSpeed, availableModes, actionMode
    # TODO: Add implementation here

    if actionMode is None:
        # No action mode set, use the default action assigned.
        if isinstance(action, list):
            # Use the first action.
            action = action[0]
    else:
        if isinstance(action, list):
            # Use the action matching the current action mode.
            matching_actions = list(filter(lambda action_command:action_command in action, actions[actionMode]))
            if len(matching_actions) == 0:
                # No matching action found, use the default action.
                action = action[0]
            else:
                # Use the matching action.
                action = matching_actions[0]

    currentTime = int(round(time() * 1000))

    # Mouse wildcard handling
    if action == 'Mouse movement wildcard':
        # if lastAction != action or  currentTime - lastActionTime > clickThresholdTime:
        if lastAction in actions['Mouse control'] and lastAction != 'Mouse movement wildcard':
            # We used mouse navigation, and now we are receiving wildcard
            # signal. So continue navigating the mouse based on lastAction
            action = lastAction

    # Typing wildcard handling
    if action == 'Typing wildcard':
        if lastAction in actions['Typing'] and lastAction != 'Typing wildcard':
            # We are typing, and now we are receiving wildcard
            # signal. So continue the typing logic
            action = lastAction

    # Navigation wildcard handling
    if action == 'Navigation wildcard':
        if lastAction in actions['Navigation control'] and lastAction != 'Typing wildcard':
            # We are using navigation controls, and now we are receiving wildcard
            # signal. So continue the navigation logic
            action = lastAction

    print(action)

    # Mouse controls
    if action == 'Move mouse left':
        if lastAction != action or  currentTime - lastActionTime > mouseStopThresholdTime:
            mouseSpeed = mouseInitialSpeed
        else:
            mouseSpeed = min(mouseSpeed + mouseAcceleration, mouseMaxSpeed)
        mouse.move(-mouseSpeed, 0)
    elif action == 'Move mouse right':
        if lastAction != action or  currentTime - lastActionTime > mouseStopThresholdTime:
            mouseSpeed = mouseInitialSpeed
        else:
            mouseSpeed = min(mouseSpeed + mouseAcceleration, mouseMaxSpeed)
        mouse.move(mouseSpeed, 0)
    elif action == 'Move mouse up':
        if lastAction != action or  currentTime - lastActionTime > mouseStopThresholdTime:
            mouseSpeed = mouseInitialSpeed
        else:
            mouseSpeed = min(mouseSpeed + mouseAcceleration, mouseMaxSpeed)
        mouse.move(0, -mouseSpeed)
    elif action == 'Move mouse down':
        if lastAction != action or  currentTime - lastActionTime > mouseStopThresholdTime:
            mouseSpeed = mouseInitialSpeed
        else:
            mouseSpeed = min(mouseSpeed + mouseAcceleration, mouseMaxSpeed)
        mouse.move(0, mouseSpeed)

    elif action == 'Mouse left click':
        if lastAction != action or  currentTime - lastActionTime > clickThresholdTime:
            mouse.click(MouseButton.left, 1)
    elif action == 'Mouse right click':
        if lastAction != action or  currentTime - lastActionTime > clickThresholdTime:
            mouse.click(MouseButton.right, 1)
    elif action == 'Mouse double click':
        if lastAction != action or  currentTime - lastActionTime > clickThresholdTime:
            mouse.click(MouseButton.left, 2)


    # Keyboard actions
    elif action == 'Space':
        if lastAction != action or  currentTime - lastActionTime > thresholdTime:
            keyboard.press(Key.space)
            keyboard.release(Key.space)
    elif action == 'Enter':
        if lastAction != action or  currentTime - lastActionTime > thresholdTime:
            keyboard.press(Key.enter)
            keyboard.release(Key.enter)
    elif action == 'Backspace':
        if lastAction != action or  currentTime - lastActionTime > thresholdTime:
            keyboard.press(Key.backspace)
            keyboard.release(Key.backspace)
    elif action == 'Escape':
        if lastAction != action or  currentTime - lastActionTime > thresholdTime:
            keyboard.press(Key.esc)
            keyboard.release(Key.esc)

    # App commands
    elif action == 'Quit':
        if lastAction != action or  currentTime - lastActionTime > thresholdTime:
            window.after(0, lambda: show_toast(window, 'Stopping remote control', on_close=exitApplication))
    elif action == 'Mode':
        if lastAction != action or  currentTime - lastActionTime > thresholdTime:
            if len(availableModes) > 1:
                if actionMode is None:
                    # Assign the first mode
                    actionIndex = 0
                else:
                    # Assign the next mode
                    actionIndex = (availableModes.index(actionMode) + 1) % len(availableModes)
                actionMode = availableModes[actionIndex]
            window.after(0, lambda: show_toast(window, f'Switched to {actionMode} mode', timeout=3000))

    # Navigation controls
    elif action == 'Up arrow':
        if lastAction != action or  currentTime - lastActionTime > thresholdTime:
            keyboard.press(Key.up)
            keyboard.release(Key.up)
    elif action == 'Down arrow':
        if lastAction != action or  currentTime - lastActionTime > thresholdTime:
            keyboard.press(Key.down)
            keyboard.release(Key.down)
    elif action == 'Left arrow':
        if lastAction != action or  currentTime - lastActionTime > thresholdTime:
            keyboard.press(Key.left)
            keyboard.release(Key.left)
    elif action == 'Right arrow':
        if lastAction != action or  currentTime - lastActionTime > thresholdTime:
            keyboard.press(Key.right)
            keyboard.release(Key.right)

    # Typing actions
    elif action == 'Type 0':
        if lastAction != action or  currentTime - lastActionTime > thresholdTime:
            keyboard.press('0')
            keyboard.release('0')
    elif action == 'Type 1':
        if lastAction != action or  currentTime - lastActionTime > thresholdTime:
            keyboard.press('1')
            keyboard.release('1')
    elif action == 'Type a b c 2':
        performTyping(action)
    elif action == 'Type d e f 3':
        performTyping(action)
    elif action == 'Type g h i 4':
        performTyping(action)
    elif action == 'Type j k l 5':
        performTyping(action)
    elif action == 'Type m n o 6':
        performTyping(action)
    elif action == 'Type p q r s 7':
        performTyping(action)
    elif action == 'Type t u v 8':
        performTyping(action)
    elif action == 'Type w x y z 9':
        performTyping(action)
    
    lastAction = action
    lastActionTime = int(round(time() * 1000))



def drawUI():
    global commandBoxText, toggleBtnText, messageLabelText, performActionFlag, autoStartFlag

    window.geometry(str(windowSize[0]) + "x" + str(windowSize[1]) + "+" + str(windowLocation[0]) + "+" + str(windowLocation[1]) + "")
    window.title(windowTitle)
    window.configure(background=color['Background'])
    
    # Spacer 
    Label(window,font=("times new roman",20),bg=color['Background'],fg=color['NormalText'], width=30).grid(row=0,columnspan=2,sticky=W+E+N+S,padx=5,pady=5)

    # Label to display decodedSignal / messages
    messageLabelText = StringVar()
    messageLabel = Label(window,textvariable=messageLabelText,font=("times new roman",15),bg=color['Background'],fg=color['NormalText'], width=30)
    messageLabel = Label(window,textvariable=messageLabelText,font=("times new roman",15),bg=color['Background'],fg=color['NormalText'], width=30)
    messageLabel.grid(row=1,columnspan=2,sticky=W+E+N+S,padx=5,pady=5)
    
    # Dropdown component to assign an action 
    commandBoxText = StringVar(window)
    commandBoxText.set(list(commandOptions)[0])
    commandBox = OptionMenu(window,commandBoxText, *commandOptions,)
    commandBox.config(font=("times new roman",15),bg=color['Background'],fg=color['NormalText'])
    commandBox.configure(anchor='w')
    commandBox.grid(row=2,columnspan=2,sticky=W+E,padx=5,pady=5)
    
    # Save button
    Button(window,text="Save",font=("times new roman",15),bg=color['ButtonBG'],fg=color['NormalText'],command=saveCommand).grid(row=3,columnspan=2,sticky=W+E+N+S,padx=5,pady=5)

    # Spacer 
    Label(window,font=("times new roman",20),bg=color['Background'], width=30).grid(row=4,columnspan=2,sticky=W+E+N+S,padx=5,pady=5)

    # Perform action check button
    performActionFlag = IntVar()
    # checkBox = Checkbutton(window,variable=performActionFlag,text='Enable actions',font=("times new roman",15),bg=color['ButtonBG'],fg=color['NormalText'],command=togglePerformAction)
    checkBox = Checkbutton(window,variable=performActionFlag,text='Enable actions',font=("times new roman",15),bg=color['Background'],fg=color['NormalText'])
    checkBox.grid(row=5,columnspan=2,sticky=W+E+N+S,padx=5,pady=5)

    # Start / Stop IR receiver button 
    toggleBtnText = StringVar()
    toggleBtnText.set('Start')
    toggleBtn = Button(window,textvariable=toggleBtnText,font=("times new roman",15),bg=color['ButtonBG'],fg=color['NormalText'],command=toggleIRThread)
    toggleBtn.grid(row=6,columnspan=2,sticky=W+E+N+S,padx=5,pady=5)

    # Reset button
    Button(window,text="Reset",font=("times new roman",15),bg=color['ButtonBG'],fg=color['NormalText'],command=resetConfiguration).grid(row=7,columnspan=2,sticky=W+E+N+S,padx=5,pady=5)
    
    # Exit button
    Button(window,text="Exit",font=("times new roman",15),bg=color['ButtonBG'],fg=color['NormalText'],command=exitApplication).grid(row=8,columnspan=2,sticky=W+E+N+S,padx=5,pady=5)

    if autoStartFlag:
        autoStartFlag = False
        # UI is hidden, so automatically start the detection.
        toggleIRThread()

        # Perform action check button
        performActionFlag.set(1)


    window.mainloop()

def main():
    global configMap
    try:
        with open(PICKLE_FILE_PATH, 'rb') as handle:
            configMap = pickle.load(handle)
            print(configMap)
    except:
        configMap = {}
    drawUI()

if __name__ == '__main__':
    main()
