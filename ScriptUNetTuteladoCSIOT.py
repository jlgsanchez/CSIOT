import subprocess
import paho.mqtt.client as mqtt
import ssl   
import psutil

# Funcion para obtener el pid de un proceso por una palabra 
def obtener_pids(palabra):
    pids = []
    for proc in psutil.process_iter(['pid', 'cmdline']):
    	pid = proc.info['pid']
    	cmdline = "".join(proc.info['cmdline']) if proc.info['cmdline'] else ""
    	if palabra.lower() in cmdline.lower():
    	    pids.append(pid)
    return pids

Unet_topic = 'SlowHedgehog/control/UNet' 
errors = 'SlowHedgehog/errores'

# Definir la función para manejar los mensajes recibidos
def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    pidsRedirecc = []
    pidsOpenvp = []
    
    if topic == Unet_topic:
        if payload == 'r':
            subprocess.run(['sudo', 'reboot'], stdout=subprocess.PIPE)
            print('UNet reboot initiated.')
            
        elif payload == 'Actredireccionpuerto':
            comando = ['ssh', 'unetudc@193.147.81.150', '-p', '2213', '-N', '-R', '55610:localhost:11194']
            proceso = subprocess.Popen(comando)  # Redirección 
            print('Redirección de puerto activado.')
            
        elif payload == 'Desactredireccionpuerto':
            pidsRedirecc = obtener_pids("sshunetudc") # Obtener pid del proceso de redirección
            if pidsRedirecc :
                subprocess.run(['kill', '-9', str(pidsRedirecc[0])])
                pidsRedirecc = []
                print('Redirección de puerto desactivado.')
            else:
                client.publish(errors, "No se tiene PID válido del proceso de redireccion") # Errores que se producen
                print('Error al desactivar la redirección de puerto.')
            	
        elif payload == 'Actopenvpn':
            comando = ['sudo', 'openvpn', '/home/jose/Documentos/CSiot/openvpn_server_UNet.ovpn']
            proceso = subprocess.Popen(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # Redirección 
            print('OpenVPN activada.')
            
        elif payload == 'Desactopenvpn':
            pidsOpenvp = obtener_pids("openvpn") # Obtener pid del proceso de redirección
            if pidsOpenvp is not None:
            	for pidopenvpn in pidsOpenvp:
                	subprocess.run(['sudo', 'kill', '-9', str(pidopenvpn)], stdout=subprocess.DEVNULL)
            	pidOpenvp = []
            	print('OpenVPN desactivada.')
            else:
                client.publish(errors, "No se tiene PID válido del proceso de OpenVPN") # Errores que se producen
                print('Error al desactivar la redirección de puerto.')


# MQTT settings
broker = 'mqtt.armriot.com'  # replace with broker
port = 8883
certCA = '/home/jose/Documentos/CSiot/certCA.crt'
# Create a client instance
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
client.username_pw_set("SlowHedgehog", "SlowHedgehog")
client.tls_set(certCA, tls_version=ssl.PROTOCOL_TLSv1_2)
client.on_message = on_message  # Asignar la función de manejo de mensajes

try:
    # Connect to the broker
    client.connect(broker, port)
    
    # Suscribirse a los temas de interés
    client.subscribe(Unet_topic)

    client.loop_forever()
        
except Exception as e:
    print(f'An error occurred: {e}')
finally:
    # Desconectar del broker
    client.disconnect()
    
