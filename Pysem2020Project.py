import bpy
from math import pi
from flask import Flask
from flask_sockets import Sockets                                                   
import threading
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler

# flask sockets app
app = Flask(__name__)
sockets = Sockets(app)
@app.route("/")

# ===============================================
# measurement processing

# handles scattering datapoints around 2pi
def handleInput(a_avg, rot_data):
    n = len(a_avg)
    
    for x in range(0, 3):
        delta = a_avg[n-1][x] - rot_data[x]
        
        if delta > pi:
            rot_data[x] += 2*pi
                
    a_avg[n-1] = rot_data

# SMA calculation
def calculateAverage(a_avg):
    avg = [0.0, 0.0, 0.0]
    
    for rot in a_avg: 
        avg[0] += rot[0]
        avg[1] += rot[1]
        avg[2] += rot[2]
        
    avg = [(x/len(a_avg)) for x in avg]
    
    return avg

# ===============================================
# sensor data processing

# receive rotation sensor data
@sockets.route('/orientation')
def echo_socket(ws):
    # objects for moving average calculation
    n = 15
    
    a_avg = [[0.0, 0.0, 0.0] for i in range(0, n)]
    
    while True:
        message = ws.receive()
        
        active_obj = bpy.context.view_layer.objects.active
        
        rot_data = [float(x)*(pi/180) for x in message.split(",")]
        
        # rotation data -ZYX to blender XYZ
        tmp = rot_data[2]
        rot_data[2] = rot_data[0] * -1 - 1.40 # - 80 degrees to compensate desk orientation
        rot_data[0] = tmp
        
        # gather past n data-trios for moving average
        for x in range(0, n-1):
            a_avg[x] = a_avg[x+1]

        handleInput(a_avg, rot_data)
        
        active_obj.rotation_euler = calculateAverage(a_avg)
        
    f.close()
    
# receive accelerometer data
@sockets.route('/accelerometer')
def echo_socket(ws):
    
    while True:
            message = ws.receive()
            
            active_obj = bpy.context.view_layer.objects.active
            
            acc_data = [float(x) for x in message.split(",")]
            
            # subtract average idle accelerometer data for phones real idle state
            acc_data[0] -= 0.04678
            acc_data[1] -= 0.10957
            acc_data[2] -= 9.80338
            
            # switch X with Y for my setup
            tmp = acc_data[0]
            acc_data[0] = acc_data[1]
            acc_data[1] = -tmp
            
            # acceleration to displacement
            period = 0.1063 # seconds
            scale = 10 # scale
            loc_data = [(x * period**2)/2 * scale for x in acc_data]
            
            for x in range(0,3):
                active_obj.location[x] += loc_data[x]
            
    f.close()

# ===============================================    
# thread functions
def startFlaskThread():
    global server
    print("Start Sensor Data Receiver")
    server = pywsgi.WSGIServer(('0.0.0.0', 5000), app, handler_class=WebSocketHandler)
    server.serve_forever()

def stopFlaskThread():
    print("Stop Sensor Data Receiver")
    server.stop()
    server.close()
    
# ===============================================
# blender custom operators
class StartSensorListen(bpy.types.Operator):
    bl_idname = "object.start_sensor_listen"
    bl_label = "Start Sensor Listen"
    
    def execute(self, context):
        threading.Thread(target=startFlaskThread).start()
        return {'FINISHED'}

class StopSensorListen(bpy.types.Operator):
    bl_idname = "object.stop_sensor_listen"
    bl_label = "Stop Sensor Listen"
    
    def execute(self, context):
        stopFlaskThread()
        return {'FINISHED'}

class ZeroActiveObj(bpy.types.Operator):
    bl_idname = "object.zero_active_obj"
    bl_label = "Zero Active Object"
    
    def execute(self, context):
        bpy.context.view_layer.objects.active.location = [0.0, 0.0, 0.0]
        bpy.context.view_layer.objects.active.rotation_euler = [0.0, 0.0, 0.0]
        return {'FINISHED'}
    
# ===============================================
# blender custom panel
class PysemPanel(bpy.types.Panel):
    bl_idname = "PANEL_PT_TestPanel"
    bl_label = "Pysem Project"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PysemProject"
    
    # function is executed for any activity in the view
    def draw(self, context):
        layout = self.layout
        
        # focus on the last selected object
        object = bpy.context.active_object

        row = layout.row()
        row.label(text="Active object:")
        if object:
            row.label(text=object.name, icon="CUBE")
        else:
            row.label(text="Nothing selected", icon = "OUTLINER_OB_MESH")
        
        row = layout.row()
        row.operator("object.zero_active_obj", text="Zero Active Object")
        
        # flask server thread control
        row = layout.row()
        row.label(text="Sensor data listener")
        row = layout.row()
        row.operator("object.start_sensor_listen", text="Start")
        row.operator("object.stop_sensor_listen", text="Stop")

# ===============================================
# blender custom class (un)registration       
def register():
    bpy.utils.register_class(ZeroActiveObj)
    bpy.utils.register_class(PysemPanel)
    bpy.utils.register_class(StopSensorListen)
    bpy.utils.register_class(StartSensorListen)
def unregister():
    bpy.utils.unregister_class(ZeroActiveObj)
    bpy.utils.unregister_class(PysemPanel)
    bpy.utils.unregister_class(StopSensorListen)
    bpy.utils.unregister_class(StartSensorListen)
    
# ===============================================
# start here
if __name__ == "__main__":
    register()
