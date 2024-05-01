import subprocess
import paho.mqtt.client as mqtt
import time
import json
import psutil
import re
import ssl

# Funcion para ejecutar el comando netstat y obtener la salida
def get_netstat_output():
    #result = subprocess.run(['netstat', '-tuln'], stdout=subprocess.PIPE)
    #return result.stdout.decode('utf-8')
    
    # Obtener la salida de netstat -tuln
    command_result = subprocess.run(['netstat', '-tuln'], stdout=subprocess.PIPE)
    netstat_output = command_result.stdout.decode('utf-8')

    # Dividir las líneas de la salida
    lines = netstat_output.split('\n')

    # Lista para almacenar los puertos abiertos
    open_ports = []

    # Iterar sobre las líneas y extraer la información de los puertos abiertos
    for line in lines:
        if 'LISTEN' in line:
            parts = line.split()
            protocol = parts[0]
            local_address = parts[3]
            port = local_address.split(':')[-1]
            open_ports.append({'protocol': protocol, 'port': port})

    return open_ports

# Function para obtener el consumo de recursos
def get_resource_consumption():
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    disk_usage = psutil.disk_usage('/')
    return {'cpu_usage': cpu_usage, 'memory_info': memory_info._asdict(), 'disk_usage': disk_usage._asdict()}
    
# Funcion para tranformar los valores de red a otros tamaños
def get_size(bytes):
    for unit in ['', 'K', 'M', 'G', 'T', 'P']:
        if bytes < 1024:
            return f"{bytes:.2f}{unit}B"
        bytes /= 1024
        
# Funcion para obtener el uso y velocidad de red
def get_network_consumption():
    # Obtener estadísticas de red
    io = psutil.net_io_counters()
    # extraer los bytes totales enviados y recibidos
    bytes_sent, bytes_recv = io.bytes_sent, io.bytes_recv
    
    time.sleep(1)

    # obtener las estadísticas nuevamente
    io_2 = psutil.net_io_counters()
    # nuevo - viejo estadísticas nos da la velocidad
    us, ds = io_2.bytes_sent - bytes_sent, io_2.bytes_recv - bytes_recv
    
    sent, recv, upload, download = get_size(io_2.bytes_sent), get_size(io_2.bytes_recv), get_size(us / 1), get_size(ds / 1)
    
    # preparar los datos de uso de red
    return {
        "bytes_sent": sent,
        "bytes_recv": recv,
        "upload_speed": upload,
        "download_speed": download
    }
    
# Función para obtener y enviar el estado de UFW por MQTT
def get_ufw_status():
    # Ejecutar el comando 'ufw status numbered'
    ufw_status_output = subprocess.run(['sudo', 'ufw', 'status', 'numbered'], stdout=subprocess.PIPE)
    ufw_status_output = ufw_status_output.stdout.decode('utf-8')
    
    # Dividir las líneas de la salida
    lines = ufw_status_output.split('\n')
    
    # Lista para almacenar las reglas de UFW
    ufw_rules = []
    
    # Iterar sobre las líneas y extraer las reglas de UFW
    for line in lines:
        parts = line.split()
        #if parts and parts[1].isdigit():
        if parts and re.search(r'\d', parts[1]):
            rule_number = parts[1]
            rule_info = ' '.join(parts[2:])
            ufw_rules.append({'rule_number': rule_number, 'rule_info': rule_info})
        elif parts and parts[0]=='Status:':
            ufw_rules.append({'Estado': parts[1]})
    
    return ufw_rules

def apache_access_log(log_file):
    # Expresión regular para analizar los registros de Apache
    apache_log_pattern = r'^(\S+) (\S+) (\S+) \[([\w:/]+\s[+\-]\d{4})\] "(\S+) (\S+)\s*(\S*)" (\d{3}) (\d+|-)'

    logs = []

    with open(log_file, 'r') as file:
        for line in file:
            match = re.match(apache_log_pattern, line)
            if match:
                log_data = {
                    "ip": match.group(1),
                    "client_id": match.group(2),
                    "user_id": match.group(3),
                    "date": match.group(4),
                    "method": match.group(5),
                    "endpoint": match.group(6),
                    "http_version": match.group(7),
                    "status_code": match.group(8),
                    "size": match.group(9)
                }
                logs.append(log_data)

    return logs
    
def apache_error_log(log_file):
    # Expresión regular para analizar los registros de errores de Apache
    apache_error_log_pattern = r'\[(?P<timestamp>.*?)\] \[(?P<component>.*?)\] \[pid (?P<pid>\d+):tid (?P<tid>\d+)\] (?P<message>.*)'
    logs = []

    with open(log_file, 'r') as file:
        for line in file:
            match = re.match(apache_error_log_pattern, line)
            if match:
                log_data = {
                    "timestamp": match.group(1),
                    "severity": match.group(2),
                    "pid": match.group(3),
                    "client_id": match.group(4),
                    "message": match.group(5)
                }
                logs.append(log_data)

    return logs

def get_temperature():
    with open("/sys/class/thermal/thermal_zone0/temp", "r") as file:
        temp_cpu_str = file.read().strip()
        temp_cpu = float(temp_cpu_str) / 1000.0  # Convertir a grados Celsius
        
    output = subprocess.check_output(["vcgencmd", "measure_temp"]).decode("utf-8")
    temp_gpu_str = output.split("=")[1].split("'")[0]
    temp_gpu = float(temp_gpu_str)
    
    data = {
        "cpu_temperature": temp_cpu,
        "gpu_temperature": temp_gpu
    }
    
    return data

# Preguntar Logs

netstat_topic = 'SlowHedgehog/netstat/output'  # topic para puertos
resource_topic = 'SlowHedgehog/resource/consumption'  # topic para rasp recursos
network_topic = 'SlowHedgehog/network/consumption'  # topic for rasp red
ufw_topic = 'SlowHedgehog/ufw/output'  # topic para ufw
errors = 'SlowHedgehog/errores' # Topic para errores producidos
logs_apache_access = 'SlowHedgehog/logs/apacheAccess' # Topic para enviar logs acceso
logs_apache_errors = 'SlowHedgehog/logs/apacheErrors' # Topic para enviar logs error
temperature_topic = 'SlowHedgehog/temperature' # Topic para enviar la temperatura

netstat_topic_input = 'SlowHedgehog/netstat/input' # Topic para actualizar la info de los puertos
ufw_topic_input = 'SlowHedgehog/ufw/input' # Topic para actualizar la info de las reglas ufw
control_topic_input = 'SlowHedgehog/control/input' # Topic para encender/apagar el sistema
logs_apache_input = 'SlowHedgehog/logs/apacheInput' # Topic para recibir cuando enviar


# Definir la función para manejar los mensajes recibidos
def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    
    if topic == netstat_topic_input and payload == 'actualizar info puertos':
        # Obtener la información de los puertos abiertos
        open_ports = get_netstat_output()
        # Formatear la información como un JSON
        json_output_op = json.dumps(open_ports)
        # Publicar el mensaje MQTT
        client.publish(netstat_topic, json_output_op)
        print('Netstat information updated and published successfully.')
    
    elif topic == ufw_topic_input:
        if payload == '1':
            # Habilitar UFW
            proceso = subprocess.Popen(['sudo', 'ufw', 'enable'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            res = proceso.communicate()
            client.publish(errors, res[1]) # Errores que se producen
            #subprocess.run(['sudo', 'ufw', 'enable'], stdout=subprocess.PIPE)
            print('UFW enabled successfully.')
        elif payload == '0':
            # Deshabilitar UFW
            proceso = subprocess.Popen(['sudo', 'ufw', 'disable'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            res = proceso.communicate()
            client.publish(errors, res[1]) # Errores que se producen
            #subprocess.run(['sudo', 'ufw', 'disable'], stdout=subprocess.PIPE)
            print('UFW disabled successfully.')
        elif payload == 'actualizar info ufw':
            # Obtener la información de las reglas UFW
            ufw_rules = get_ufw_status()
            # Formatear la información como un JSON
            json_output_ufw = json.dumps(ufw_rules)
            # Publicar el mensaje MQTT
            client.publish(ufw_topic, json_output_ufw)
            print('UFW information updated and published successfully.')
        else:
            node_command = payload.split()
            params = ["sudo","ufw"]
            final_command = params + node_command
            # Crear el proceso subprocess y redirigir la entrada estándar (stdin) para proporcionar la confirmación automáticamente
            proceso = subprocess.Popen(final_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Se envia la confirmación y el "enter"
            res = proceso.communicate(b'y\n')
            client.publish(errors, res[1]) # Errores que se producen
            print('Changed UFW rules.')

    elif topic == control_topic_input:
        if payload == 'r':
            subprocess.run(['sudo', 'reboot'], stdout=subprocess.PIPE)
            print('System shutdown initiated.')
        elif payload == '0':
            subprocess.run(['ssh', 'josel@192.168.1.154', 'shutdown' '/p'], stdout=subprocess.PIPE)
            print('System shutdown initiated.')
            
    elif topic == logs_apache_input and payload == 'logsApache':
        # Ruta ficheros de log
        log_access_file_path = "/var/log/apache2/access.log.1"
        log_errors_file_path = "/var/log/apache2/error.log.1"
        # Acceso y extración de los logs
        formatted_access_logs = apache_access_log(log_access_file_path)
        formatted_errors_logs = apache_error_log(log_errors_file_path)
        # Conversioón a JSON
        json_access_logs = json.dumps(formatted_access_logs)
        json_errors_logs = json.dumps(formatted_errors_logs)
        # Publicación en MQTT
        client.publish(logs_apache_access, json_access_logs)
        client.publish(logs_apache_errors, json_errors_logs)
        print('Logs sended successfully.')


# MQTT settings
broker = 'mqtt.armriot.com'  # replace with broker
port = 8883
certCA = '/home/pi/Desktop/CSIOT/ClaveMQTTBroker/certCA.crt'
# Create a client instance
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
client.username_pw_set("SlowHedgehog", "SlowHedgehog")
client.tls_set(certCA, tls_version=ssl.PROTOCOL_TLSv1_2)
#client.connect('mqtt.armriot.com', 8883, 60)
client.on_message = on_message  # Asignar la función de manejo de mensajes

try:
    # Connect to the broker
    client.connect(broker, port)
    
    # Suscribirse a los temas de interés
    client.subscribe(netstat_topic_input)
    client.subscribe(ufw_topic_input)
    client.subscribe(control_topic_input)
    client.subscribe(logs_apache_input)

    # Iniciar el bucle de manejo de eventos MQTT en un hilo separado
    client.loop_start()
    
    # Obtener la información de los puertos abiertos
    open_ports = get_netstat_output()
    # Formatear la información como un JSON
    json_output_op = json.dumps(open_ports)
    # Publicar el mensaje MQTT
    client.publish(netstat_topic, json_output_op)
    
    print('Open ports information published successfully.')
    
    
    # Obtener la información de las reglas UFW
    ufw_rules = get_ufw_status()
    # Formatear la información como un JSON
    json_output_ufw = json.dumps(ufw_rules)
    # Publicar el mensaje MQTT
    client.publish(ufw_topic, json_output_ufw)
    
    print('UFW rules information published successfully.')

    #netstat_timer = 0
    resource_timer = 0
    network_timer = 0

    while True:
        #if netstat_timer % 30 == 0:
            # Get the netstat output
            #netstat_output = get_netstat_output()

            # Format the output as a JSON object
            #json_output = json.dumps({'netstat': netstat_output})

            # Publish the message
            # client.publish(netstat_topic, json_output)
            #client.publish(netstat_topic, netstat_output)

            #print('Netstat message published successfully.')

        if resource_timer % 5 == 0: # 3600
            # Obtener el consumo de recursos y las temperaturas 
            resource_consumption = get_resource_consumption()
            temperatures = get_temperature()

            # Formateo de la salida a un objeto JSON
            json_output = json.dumps(resource_consumption)
            json_output_temp = json.dumps(temperatures)
            
            # Publica los mensajes
            client.publish(resource_topic, json_output)
            client.publish(temperature_topic, json_output_temp)
            
            print('Resource consumption message published successfully.')
            print('Temperature message published successfully.')
            
        if network_timer % 3 == 0:  # 3000
            # Obtener el uso de red
            network_consumption = get_network_consumption()

            # Formateo de la salida a un objeto JSON
            json_output_n = json.dumps(network_consumption)

            # Publica los mensajes
            client.publish(network_topic, json_output_n)
            
            print('Network consumption message published successfully.')
            

        # Espera por 1 segundo
        time.sleep(1)

        # Incrementa los timers
        #netstat_timer += 1
        resource_timer += 1
        network_timer += 1
    client.loop_forever()
        
except Exception as e:
    print(f'An error occurred: {e}')
finally:
    # Desconectar del broker
    client.disconnect()
    
