# Flipperzero-StepCounter-fap
This is a simple StepCounter/Pedometer for FlipperZero using a Memsic2125 module. 
> Thanks to @jamisonderek for the tutorial on how to implement Memsic2125 module on Flipper Zero, and for the support.

# Links  
<img src="https://raw.githubusercontent.com/grugnoymeme/flipperzero-StepCounter-fap/main/images/memsic_2125_chip.jpg" width="200" />

| Mx2125 | Name | Purpose | Flipper |
|--------|------|---------|---------|
|Pin 1 | Tout | Temperature Out | not connected|
|Pin 2 | Yout | Y-axis PWM Out (100Hz, duty cycle = value) | C0|
|Pin 3 | GND | Ground | GND|
|Pin 4 | GND | Ground | GND|
|Pin 5 | Xout | X-axis PWM Out (100Hz, duty cycle = value) | C1|
|Pin 6 | Vdd | Drain voltage (3.3V to 5V DC) | 3v3|

# Screenshots   
![Main menu view](https://raw.githubusercontent.com/grugnoymeme/flipperzero-StepCounter-fap/main/images/menu_view.png "main menu view")

![Main screen](https://raw.githubusercontent.com/grugnoymeme/flipperzero-StepCounter-fap/main/images/main_screen.png "main screen view")


TODO List:
- [ ] Add an INFO window with the link to the original Repo and the Pinout connection between the Flipper Zero and the Memsic Mx2125 module
- [ ] Add a simple animation of a Dolphin Runner     
- [ ] Add a management of the possible errors           
- [ ] Add the possibility to restart the counting             
- [ ] Add the possibility to set a daily/weekly GOAL to reach
- [ ] Add the possibility to save dayly results in files at the path: apps_data/stepcounter, to comtìpare them and improve (interacting with calendar FAP? maybe...)
