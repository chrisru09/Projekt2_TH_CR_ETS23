"""
autor: 	Rudolf, Christian
        Heikebrügge, Tim
datum: 09.04.2024
Funktionsbeschreibung :

​​Smart Home System​​
Unser Kunde wünscht sich ein Smarthome-System mit folgenden Komponenten:
Mit einem Helligkeitssensor die Helligkeit im Wohnzimmer feststellen um dann ggf. den virtuellen Raum abzudunkeln mit Rolläden.
Sauerstoffgehalt im Wohnzimmer ermitteln und dann ein virtuelles Fenster öffnen um zu lüften
Wenn die Anlage "scharf" geschaltet wird, soll ein Alarm ausgeben werden, wenn ein Bewegungsmelder ausgelöst wird. 
Info für  Temperatur der Heizung und etc.
Visualisierung über Node-RED darstellen.
Zusätzlich werden die Temperatur und der Co 2-Gehalt in einer Datenbank abgelegt.


Versionsnummer: 1.0
Hardware :      Espressif ESP32-S3-WROOM-1
                1x Co2 Sensor (SDC30)
                1x Helligkeitssensor (BH1750)
                1x Temperatursensor (AHT10)
                1x Bewegungssensor (SEN-HC-SR501)
                5x Weiße LED´s 220 Ohm Widerstand (Jalousie höhe)
                3x LED´s 220 Ohm Widerstand (Alarmstatus)
                1x LED 220 Ohm Widerstand (Fenster Auf)
                1x Taster 10k Ohm Widerstand Pull-Down (Alarmanlage De-/Aktivieren)
Software:	MQTT
            Node-red
            Heidisql
            MariaDB
Bilbiothekenname : scd30.py (Co2 Sensor), bh1750.py (Helligkeitssensor), ahtx0.py (Temperatursensor)

Temperatursensor Anschluss :	VCC = 3.3V
                                GND = GND
                                SCL = GPIO39
                                SDA = GPIO38
Helligkeitssensor Anschluss :	VCC = 3.3V
                                GND = GND
                                SCL = GPIO39
                                SDA = GPIO38
Co2 Sensor Anschluss:			VIN = 3.3V
                                GND = GND
                                SCL = GPIO39
                                SDA = GPIO38
Bewegungssensor Anschluss:		VCC = 3.3V
                                GND = GND
                                OUT = GPIO9

"""
#-------------------------------------------------------------------------------------------------
#Bibliotheken Importieren

from machine import Pin, SoftI2C
import time
from time import sleep

import json
from umqtt.simple import MQTTClient

#Netzwerk
import network
import ubinascii
import machine

#Import Temperatursensor Library
import ahtx0

#Import Co2 Library
from scd30 import SCD30

#Import Lichtstärke Library
from bh1750 import BH1750



#-------------------------------------------------------------------------------------------------
#Pins definieren
#Fenster
fensterAuf = Pin(3, Pin.OUT)

#Alarmanlage
bewegungsSensor = Pin(9, Pin.IN, Pin.PULL_DOWN)
tasterAlarm = Pin(8, Pin.IN)
ledRot = Pin(15, Pin.OUT)
ledGruen = Pin(16, Pin.OUT)
ledBlau = Pin(17, Pin.OUT)

#jalousie
ledjalousie25 = Pin(4, Pin.OUT)
ledjalousie50 = Pin(5, Pin.OUT)
ledjalousie75 = Pin(6, Pin.OUT)
ledjalousie100 = Pin(7, Pin.OUT)

#I2C-Bus definieren
i2c_sda = Pin(38)
i2c_scl = Pin(39)
I2C = SoftI2C(sda=i2c_sda, scl=i2c_scl)

#Luftfeuchtigkeit- und Temperatur- erfassung
sensorAhtx0 = ahtx0.AHT10(I2C)

#Helligkeitserfassung
helligkeit = BH1750(0x23, I2C)

#Co2 Datenerfassung
sauerstoff = SCD30(I2C, 0x61)

#-------------------------------------------------------------------------------------------------
#Variablen

#Alarmanlage
tasterStatus = False
tastergedrueckt = False
tasterwar_aus = False
alarmEin = False 
alarmmanuell = ["Alarmanlage deaktiviert"]


#Jalousie
jalousiemanuell = [""]
jalousieAutomatik = ["Jalousie Automatik Aus"]
jalousieAutomatik_Wert = 4000
jalousiehoehe = 0

#Fenster
fenstermanuell = ["geschlossen"]
fensterAutomatik = ["Fenster Automatik Aus"]
fensterAutomatik_Wert = 40
fensterAutomatik_co2_Wert = 3000
temperatur_AHTX = 0
luftfeuchte_AHTX = 0
fensterStatus = False

#Zeitdifferenz Anfangswerte für Zeitabfrage ohne sleep()
zeit_alt_temp = 0
zeit_alt_rel = 0
zeit_alt_hell = 0
zeit_alt_co2 = 0
zeit_alt_taster = 0
zeit_alt_mqtt = 0
zeit_alt_read = 0


#-------------------------------------------------------------------------------------------------
# Wifi Verbindung

# wlan_ssid = "BZTG-IoT"
# wlan_passwort = "WerderBremen24"
wlan_ssid = "FRITZ!Box 5530 R"
wlan_passwort = "98755767599735437457"


#Mit Wlan verbinden
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(wlan_ssid, wlan_passwort)

#Auf Wlan Verbindung warten
while not wlan.isconnected():
    pass

#SSID und IP ausgeben in Konsole
print("--------------------------------------------------------------")
print("Verbunden mit", wlan_ssid)
print("IP-Adresse vom ESP:", wlan.ifconfig()[0])
print("--------------------------------------------------------------")


#-------------------------------------------------------------------------------------------------
# MQTT Broker Verbindung
client_id = ubinascii.hexlify(machine.unique_id()) #Eindeutigen namen vergeben
server = "192.168.178.76"  #MQTT Broker IP
topic = "SMARTHOME_T&C"	#Topic einstellen

c = MQTTClient(client_id, server) #MQTT Funktion in Variable "c" schreiben
c.connect()	#Verbindung herstellen
print("--------------------------------------------------------------")
print(f"Verbunden mit {server}")
print("--------------------------------------------------------------")


# Nachrichten aus dem MQTT Broker empfangen und in Variablen schreiben
def mqtt_nachricht(topic, message):
    global jalousiemanuell, alarmmanuell, fenstermanuell, fensterAutomatik, fensterAutomatik_Wert, jalousieAutomatik, jalousieAutomatik_Wert, fensterAutomatik_co2_Wert
    try:
        msg_neu = json.loads(message.decode())
        if "Status" in msg_neu:					#Alarmanlage über Website Ein-/Ausschalten
            alarmmanuell = msg_neu["Status"]
        if "Befehl" in msg_neu:            		#Jalousie über Website steuern
            jalousiemanuell = msg_neu["Befehl"]
        if "Fenster" in msg_neu:				#Fenster über Website Öffnen/Schließen
            fenstermanuell = msg_neu["Fenster"]
        if "Fenster_Auto" in msg_neu:			#Fenstersteuerung auf Automatik 
            fensterAutomatik = msg_neu["Fenster_Auto"]
        if "Fenster_Auto_Wert" in msg_neu:		#Fenstersteuerung ab welchem Tempwert soll geöffnet/geschlossen werden
            fensterAutomatik_Wert = msg_neu["Fenster_Auto_Wert"]
        if "Fenster_Auto_co2_Wert" in msg_neu:	#Fenstersteuerung ab welchem Co2wert soll geöffnet/geschlossen werden
            fensterAutomatik_co2_Wert = msg_neu["Fenster_Auto_co2_Wert"]
        if "Jalousie_Auto" in msg_neu:			#Jalousiesteuerung auf Automatik
            jalousieAutomatik = msg_neu["Jalousie_Auto"]
        if "Jalousie_Auto_Wert" in msg_neu:		#Jalousiesteuerung ab welchem Lumenwert soll geöffnet/geschlossen werden
            jalousieAutomatik_Wert = msg_neu["Jalousie_Auto_Wert"]
        
        
        #Werte zur Prüfung in Konsole ausgeben
        print("--------------------------------------------------------------")
        print("Jalousie Status:", jalousiemanuell)
        print("Alarm Status:", alarmmanuell)
        print("Fenster Status:",fenstermanuell)
        print("Fenster Automatik:", fensterAutomatik)
        print("Fenster Automatik Temperatur Wert:", fensterAutomatik_Wert)
        print("Fenster Automatik Co2 Wert:", fensterAutomatik_co2_Wert)
        print("Jalousie Automatik:", jalousieAutomatik)
        print("Jalousie Automatik Wert:", jalousieAutomatik_Wert)
        print("--------------------------------------------------------------")
    except Exception as e:
        print("Fehler beim Parsen der Nachricht:", e)
    


#-------------------------------------------------------------------------------------------------

# Aufrufen der Funktion mqtt_nachricht
c.set_callback(mqtt_nachricht)
# Topic abonnieren
c.subscribe(topic)

while True:
#-------------------------------------------------------------------------------------------------
# Auf Nachrichten im MQTT-Broker prüfen
    zeit_now_read = time.ticks_ms()
    if(time.ticks_diff(zeit_now_read, zeit_alt_read) > 1000):
        c.check_msg()
        zeit_alt_read = time.ticks_ms()
#-------------------------------------------------------------------------------------------------       
# Fenstersteuerung
    if fensterAutomatik == "Fenster Automatik Aus":  
        if fenstermanuell == "geoeffnet":
            fensterAuf.on()
            fensterStatus = True
        if fenstermanuell == "geschlossen":
            fensterAuf.off()
            fensterStatus = False

    if fensterAutomatik == "Fenster Automatik Ein":
        if temperatur_AHTX >= fensterAutomatik_Wert or co2 >= fensterAutomatik_co2_Wert:
            fensterAuf.on()
            fensterStatus = True
        else:
            fensterAuf.off()
            fensterStatus = False

#-------------------------------------------------------------------------------------------------
# Jalousie
    if jalousieAutomatik == "Jalousie Automatik Aus":
        if jalousiemanuell == "25% Jalousie":
            ledjalousie25.on()
            ledjalousie50.off()
            ledjalousie75.off()
            ledjalousie100.off()
            
        if jalousiemanuell == "50% Jalousie":
            ledjalousie25.on()
            ledjalousie50.on()
            ledjalousie75.off()
            ledjalousie100.off()
            
        if jalousiemanuell == "75% Jalousie":
            ledjalousie25.on()
            ledjalousie50.on()
            ledjalousie75.on()
            ledjalousie100.off()

        if jalousiemanuell == "100% Jalousie":
            ledjalousie25.on()
            ledjalousie50.on()
            ledjalousie75.on()
            ledjalousie100.on()
            
        if jalousiemanuell == "0% Jalousie":
            ledjalousie25.off()
            ledjalousie50.off()
            ledjalousie75.off()
            ledjalousie100.off()
            
    if jalousieAutomatik == "Jalousie Automatik Ein":
        jalousiemanuell = ""
        if helligkeit_BH1750 >= jalousieAutomatik_Wert:
            ledjalousie100.on()
            ledjalousie75.on()
            ledjalousie50.off()
            ledjalousie25.off()  
        else:
            ledjalousie100.off()
            ledjalousie75.off()
            ledjalousie50.off()
            ledjalousie25.off()

#------------------------------------------------------------------------------------------------- 
# Alarmanlage

# Tasterabfrage
    tastergedrueckt = tasterAlarm.value()
    zeit_now_taster = time.ticks_ms()
    bewegung = bewegungsSensor.value()
    bewegMeldung = False 
    
    if tastergedrueckt or alarmmanuell == "Alarmanlage aktiviert" or (alarmmanuell == "Alarmanlage deaktiviert" and tasterwar_aus == True):
        if(time.ticks_diff(zeit_now_taster, zeit_alt_taster) > 300):
            tasterStatus = not tasterStatus
            tasterwar_aus = False
            zeit_alt_taster = time.ticks_ms()
    if not tastergedrueckt:
        tasterwar_aus = True
        
# Alarmsteuerung
    if alarmmanuell == "Alarmanlage aktiviert" or tasterStatus == True:
        alarmEin = True
        alarmmanuell = []
        ledGruen.off()
        ledRot.on()
    if alarmmanuell == "Alarmanlage deaktiviert" or tasterStatus == False:
        alarmEin = False
        alarmmanuell = []
        ledRot.off()
        ledGruen.on()
        ledBlau.off()
        
    if alarmEin and bewegung == True:
        ledBlau.on()
        bewegMeldung = True 
    if alarmEin and bewegung == False:
        ledBlau.off()
        bewegMeldung = False
    

    
#-------------------------------------------------------------------------------------------------     
# Temperatur, Luftfeucht, Helligkeit messen
    zeit_now_temp = time.ticks_ms()
    if(time.ticks_diff(zeit_now_temp, zeit_alt_temp) > 5000):
        temperatur_AHTX = round(sensorAhtx0.temperature)
        luftfeuchte_AHTX = round(sensorAhtx0.relative_humidity)
        helligkeit_BH1750 = round(helligkeit.measurement)
        zeit_alt_temp = time.ticks_ms()
    

# Sauerstoffgehalt messen und richtig ausgeben
    while sauerstoff.get_status_ready() != 1:
        sleep(0.2)
        
    zeit_now_co2 = time.ticks_ms()
    if(time.ticks_diff(zeit_now_co2, zeit_alt_co2) > 5000):
        sauerstoffTuple = sauerstoff.read_measurement()
        co2 = round(sauerstoffTuple[0])
        zeit_alt_co2 = time.ticks_ms()

# Werte in JSON format verpacken
    x_json = {
        "Ort": "Haus",
        "Raum": "Wohnzimmer",
        "Sensorwerte": [
             {"Temperatur": temperatur_AHTX},   
             {"Luftfeuchte": luftfeuchte_AHTX},
             {"CO2-Gehalt": co2},
             {"Helligkeit": helligkeit_BH1750},
             {"Alarm": bewegMeldung},
             {"Alarm Status": alarmEin},
             {"Fenster Status": fensterStatus},
            ]
    }
    sorted_string = json.dumps(x_json) # Codiert die Nachricht in ein JSON-String
#-------------------------------------------------------------------------------------------------    
# Nachricht senden an MQTT Broker
    zeit_now_mqtt = time.ticks_ms()
    if(time.ticks_diff(zeit_now_mqtt, zeit_alt_mqtt) > 5000):
        c.publish(topic, sorted_string)
        print("--------------------------------------------------------------")
        print("Nachricht an MQTT-Broker gesendet.")
        print("--------------------------------------------------------------")
        zeit_alt_mqtt = time.ticks_ms()
        
   
