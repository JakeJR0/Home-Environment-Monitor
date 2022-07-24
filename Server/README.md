# Server

## Setup
To setup the server you will need to clone the repository and run the [server.py](server.py) file.

```
git clone https://github.com/JakeJR0/Home-Control.git
cd Home-Control
python server.py
```

Once the program is running the server should be setup, the server will work as intended but I would recommend
that you setup a sensor for the server to use otherwise it will not work as intended. A link to the [Sensor Documentation](../MicroController/) which would be used
to add a sensor.

### Login Details
Once the program has been run once, the program will have created the default account which has the following details:
```
  Keycard ID: 0000000000
```
Originally the program was setup to work with RFID tags as I recently purchased a [reader](https://www.amazon.co.uk/gp/product/B09K7BWWC8/ref=ppx_yo_dt_b_asin_title_o02_s00?ie=UTF8&psc=1)
and wanted to use it for some project, if you already have a reader once you have logged in you can go to account settings and change both the name and you can modify the authorised keycards.

## Notice
Please note that this project is under development and might have some unknown issues / bugs that might affect the preformance of the program.
Additionally, I have left an example of an [IFFT Webhook](https://ifttt.com/maker_webhooks) token within the [server.py](server.py) which is invalid and only used to demonstrate what a token might look like.

