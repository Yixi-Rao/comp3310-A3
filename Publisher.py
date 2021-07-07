import threading
import time
import paho.mqtt.client as mqtt

'''
    #? This file contains the publisher and the controller #?
    
    Publisher: publish counter value to topic counter/# and the behaviour is controled by the controller
    controller: using the multi-threading to achieve two programs(publisher and controller running at the same time) and using the 
                global variable to control the behaviour of the publisher.
'''

# global variable
token      = True  # the token controls the process of publishing message to counter
Qos_lock   = False # the Qos_lock will be opened when the controller recevies a message which requires the controller to change the Qos
delay_lock = False # the delay_lock will be opened when the controller recevies a message which requires the controller to change the delay
non_stop   = True  # control the whole program processing, if this is false, the whole program will terminate

Qos       = 0
delay     = 0.0
publisher = mqtt.Client(client_id='3310-u6826541', clean_session=True)

def Pub_connect(client, userdata, flags, rc):
    ''' on_connect fot the publisher
    '''
    if rc == 0:
        print("Publisher Connected to MQTT Broker!")
    else:
        print("Failed to connect, return code %d\n", rc)
        
def Con_connect(client, userdata, flags, rc):
    ''' on_connect fot the controller
    '''
    if rc == 0:
        print("Controller Connected to MQTT Broker!")
    else:
        print("Failed to connect, return code %d\n", rc)

def on_message(client, userdata, msg):
    ''' on_message fot the controller
        controller will listen two topics to decide what is the mode of the publishing
    '''
    global Qos, delay, token, Qos_lock, delay_lock, non_stop

    if msg.topic == "request/qos":
        print("----------------------------QOS--------------------------------------")
        print(str(Qos) + " should change to: " + str(msg.payload.decode('utf-8')))
        # should change the qos to a new one, and open the lock, stop the current publishment
        Qos      = int(msg.payload)
        token    = False
        Qos_lock = True
        
    elif msg.topic == "request/delay":
        print("----------------------------DELAY------------------------------------")
        print(str(delay) + " should change to: " + str(msg.payload.decode('utf-8'))) 
        # should change the delay to a new one, and open the lock, stop the current publishment
        delay = float(msg.payload)
        token = False
        delay_lock = True
        
    elif msg.topic == "request/stop":
        print("============================STOP====================================")
        # all the measurement is finish, and we can stop the whole program
        token    = False
        non_stop = False
        publisher.disconnect()
        
def run_controller():
    '''this is the thread of controller, which will listen to the broker's topic request/#
    '''
    controller = mqtt.Client(client_id='3310-1', clean_session=True)
    controller.on_connect = Con_connect
    controller.on_message = on_message
    
    #? ==============================remote broker=========================================
    controller.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)
    controller.username_pw_set("student3", "Comp3310")
    controller.connect("06862eb9e8544d06b7b9f75bdfac4a28.s1.eu.hivemq.cloud", 8883)
    #? =============================local test broker======================================
    # controller.username_pw_set("kyrie", "Ryx990916")
    # controller.connect('broker.emqx.io', 1883)
    #? ====================================================================================
    
    controller.subscribe("request/#", qos = 1)
    controller.loop_start()
    while non_stop:
        time.sleep(5)
    # controller.loop_forever()
    
def publish(client: mqtt.Client, delay: float, Qos: int):
    '''this function will ceaselessly publish counter value to counter/# until the global variable token is change

    Args:
        client (mqtt.Client): publisher
        delay (float): how often will it sends a message
        Qos (int): the qos level
    '''
    msg_count = 0
    topic = "counter/" + str(Qos) + "/" + str(delay)
    while token:
        msg    = msg_count
        result = client.publish(topic = topic ,payload = msg, qos = Qos)
        result.wait_for_publish()

        status = result[0]
        if status == 0:
            print("Send " + str(msg) +  " to " + topic)
        else:
            print("Failed to send message to " + topic)
            
        msg_count += 1
        # control the speed
        time.sleep(delay)

if __name__ == '__main__':
    #! first, create the controller thread
    Con_thread = threading.Thread(target=run_controller)
    Con_thread.start()
    print("Controller established!")
    #! second, establish publisher connection
    publisher.on_connect = Pub_connect
    publisher.on_message = on_message
    
    #? ==============================remote broker=========================================
    publisher.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)
    publisher.username_pw_set("student2", "Comp3310")
    publisher.connect("06862eb9e8544d06b7b9f75bdfac4a28.s1.eu.hivemq.cloud", 8883)
    #? =============================local test broker======================================
    # publisher.username_pw_set("kyrie", "Ryx990916")
    # publisher.connect('broker.emqx.io', 1883)
    #? ====================================================================================
    
    publisher.loop_start()
    publish(publisher, delay, Qos)
    #! last, decide the delay and Qos
    while non_stop:
        if Qos_lock and delay_lock:
            print("---------------------------------------------------------------------")
            print("=> Delay is " + str(delay) + ", Qos is " + str(Qos))
            Qos_lock = False
            delay_lock = False
            token = True
            time.sleep(0.3)
            publish(publisher, delay, Qos)

    