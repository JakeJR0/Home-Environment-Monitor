# Home Environment Monitor

## Table of Content
- [Project Information](#project-information)
- [Project Plan](#project-plan)
- [Sensors Documentation](MicroControllers)
- [Server Documentation](Server)

## Project Information
This project uses the [Flask Framework](https://github.com/pallets/flask) to make a viewable website which the user
is able to view and control the information / data provided by the sensors.

## Project Plan
The plan for this project was to create a program that can store and help alter the environment of my house without having any input from a human. My hope was that I would be able to get the project up and running before a heat wave hit the UK as I did not want to mess with the fans within my house with temperature being high. 

Overall I wanted the system to:
- Store Environment Data
- Work with mutiple people / accounts
- Control Smart Devices within the House
- Act on the environment data acquired
- Be user friendly

In general with the current version of the system I do believe that the system is meeting the requirements that I set for the project.

## Improvements
- Use https protocol (Currently the system will only work on http due to an issue with redirects within the urequests module on the sensors) 
- Add more devices to be controlled such as changing light colours
- Add [IFFT](https://ifttt.com/) integration to ensure that the system is only altering the environment when someone is at the house (To save electicity) 
- Make the website more friendly for mobile users

## Notice
Please note that this project is still in development so some aspects of this project are not yet completed.
