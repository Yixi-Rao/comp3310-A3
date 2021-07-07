import threading
import time
import paho.mqtt.client as mqtt
import itertools
import numpy as np

'''
    #? This file contains the analyser #?
    
    analyser: will first collect the data it wanted and also change the behaviour of the publisher, after all the measurement is finished
              it will analyse the data and calculate the average rate of messages received, rate of message loss, rate of any out-of-order messages
              and mean and median inter-message-gap.
'''
# global variable
analyse_data = {} # a dictionary indexed by topic name, the value is all the counter values
analyse_time = {} # a dictionary indexed by topic name, the value is all the msg received time
INTERVAL = 120    # duration of each run (for each Qos and for each delay)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Analyser connected to MQTT Broker!")
    else:
        print("Failed to connect, return code %d\n", rc)

def on_message(client, userdata, msg):
    ''' Collect statistics, for each delay and QoS level
    '''
    #! print("Received: " + str(msg.payload) + " ->  from: " + msg.topic)
    global analyse_data, analyse_time

    if msg.topic not in analyse_data:
        
        analyse_data[msg.topic] = [int(msg.payload)]
        analyse_time[msg.topic] = [float(msg.timestamp)]
    else:
        analyse_data[msg.topic].append(int(msg.payload))
        analyse_time[msg.topic].append(float(msg.timestamp))
    
def timer(Analyser):
    '''thread of Analyser publishing message to broker's topic request/#

    Args:
        Analyser (client): will change the mode
    '''
    stage = 0
    # all the delay and Qos
    delays = [0.0, 20]  #[0.0, 0.01, 0.02, 0.05, 0.1, 0.5]
    Qoses  = [0] #[0, 1, 2]
    for delay, Qos in itertools.product(delays, Qoses): 
        if delay == delays[0] and Qos == Qoses[0]:
            continue
        # wait 2 min for each run
        time.sleep(INTERVAL)
        result1 = Analyser.publish(topic = 'request/qos',   payload = Qos, qos = Qos)
        result2 = Analyser.publish(topic = 'request/delay', payload = delay, qos = Qos)
        status1 = result1[0]
        status2 = result2[0]
        if status1 == 0 and status2 == 0:
            print("-----------------------------" + str(stage) + "---------------------------------------")
            print("- Analyser publish:  delay = " + str(delay) + " to topic request/delay")
            print("- Analyser publish:  Qos   = " + str(Qos) + " to topic request/qos.")
            print("---------------------------------------------------------------------")
        else:
            print("Failed to send message to request/#")
        stage += 1
    # after all the measurement is finished, stop itself and also stop the publisher and controller   
    time.sleep(INTERVAL + 0.5)
    result = Analyser.publish(topic = "request/stop", payload = True, qos = 1)
    if result[0] == 0:
        print("Analyser disconnect")
    else:
        print("Analyser disconnect failure")
    time.sleep(1)    
    Analyser.disconnect()    

if __name__ == '__main__':
    #! first, create the Analyser
    Analyser = mqtt.Client(client_id='3310-2', clean_session=True)
    Analyser.on_connect = on_connect
    Analyser.on_message = on_message
    
    # change the host and port in here
    #? ==============================remote broker=========================================
    # Analyser.username_pw_set("student", "33102021")
    # Analyser.connect("a1zf0t2vrghftz-ats.iot.us-east-2.amazonaws.com", 1883)
    
    # Analyser.username_pw_set("student", "33102021")
    # Analyser.connect("42.192.179.225", 1883)
    #? =============================local test broker======================================
    Analyser.username_pw_set("kyrie", "Ryx990916")
    Analyser.connect("broker.emqx.io", 1883)
    #? ====================================================================================
    Analyser.subscribe('counter/0/#', qos = 0)
    Analyser.subscribe('counter/1/#', qos = 1)
    Analyser.subscribe('counter/2/#', qos = 2)

    #! second, create the timer to change the mode
    timer_thread = threading.Thread(target=timer, args=(Analyser,))
    timer_thread.start()
    print("Timer is on!")

    Analyser.loop_forever() 
    print(len(analyse_data))
    #! last, analyse the data
    rec_rate_dict = {} # a dictionary indexed by topic name, the value is recieved message rate
    gap_time_dict = {} # a dictionary indexed by topic name, the value is a list of all gap times
    mid_mean_dict = {} # a dictionary indexed by topic name, the value is a tuple of median value of all gap time and mean value of all gap time
    disorder_dict = {} # a dictionary indexed by topic name, the value is our-of-order message rate
    loss_msg_dict = {} # a dictionary indexed by topic name, the value is loss message rate
    
    for topic, data in analyse_data.items():
        #! The overall average rate of messages you actually receive across the period [messages/second]
        rec_rate_dict[topic] = len(data) / INTERVAL
        #! The mean and median inter-message-gap you see [seconds].
        gap_time_dict[topic] = [analyse_time[topic][i] - analyse_time[topic][i - 1] 
                                    for i in range(1, len(data))
                                        if data[i] == data[i - 1] + 1]
        
        mid_mean_dict[topic] = (np.median(gap_time_dict[topic]), np.mean(gap_time_dict[topic]))
        #! The rate of any out-of-order messages you see [percentage]
        disorder_dict[topic] = len(list(filter(lambda i: data[i] - data[i - 1] != 1,
                                          [x for x in range(1, len(data))]))) / len(data) if len(data) != 0 else 0
        #! The rate of message loss you see [percentage].
        topics = topic.split('/')
        if float(topics[2]) == 0.0 or float(topics[2]) == 0:
            # should_rece = max(data) - min(data) + 1
            should_rece = sum([data[i] - data[i - 1] for i in range(1, len(data))])
            loss_msg_dict[topic] = (should_rece - len(data)) / should_rece if should_rece != 0 or should_rece >= len(data) else 100
        else:
            total_msg = INTERVAL / float(topics[2])
            loss_msg_dict[topic] = (total_msg - len(data)) / total_msg if total_msg != 0 or total_msg >= len(data) else 100
    # print all the result
    for t, r in rec_rate_dict.items():
        print(t + " : receive message rate -> " + str(r) + " msg/s") 
    print(" ")       
    for t, l in loss_msg_dict.items():
        print(t + " : loss message percentage -> " + str(l) + "%")
    print(" ")
    for t, do in disorder_dict.items():
        print(t + " : disorder message percentage -> " + str(do) + "%")     
    print(" ")
    for t, mm in mid_mean_dict.items():
        print(t + " : gap msg median -> " + str(mm[0])  + "s" + " , gap msg mean -> " + str(mm[1])  + "s")  
        
# back-up broker:
    # Analyser.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)
    # Analyser.username_pw_set("student1", "Comp3310")
    # Analyser.connect("06862eb9e8544d06b7b9f75bdfac4a28.s1.eu.hivemq.cloud", 8883)
    
    # Analyser.username_pw_set("student", "33102021")
    # Analyser.connect("42.192.179.225", 1883)
    
    # Analyser.username_pw_set("student", "33102021")
    # Analyser.connect("a1zf0t2vrghftz-ats.iot.us-east-2.amazonaws.com", 1883)