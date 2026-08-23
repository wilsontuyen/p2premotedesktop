import re

# 1. Update UPnPManager.kt to require Context and use MulticastLock
upnp_file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\UPnPManager.kt'
with open(upnp_file, 'r', encoding='utf-8') as f:
    upnp_content = f.read()

new_upnp_content = """package com.example.p2pdroidremote

import android.content.Context
import android.net.wifi.WifiManager
import android.util.Log
import org.bitlet.weupnp.GatewayDiscover
import org.bitlet.weupnp.GatewayDevice
import org.bitlet.weupnp.PortMappingEntry
import kotlin.concurrent.thread
import java.net.InetAddress

object UPnPManager {
    private const val TAG = "UPnPManager"
    private var activeDevice: GatewayDevice? = null
    private var activePort: Int = -1

    fun openPortBackground(context: Context, port: Int, maxAttempts: Int = 3) {
        thread(name = "UPnP-Thread") {
            var multicastLock: WifiManager.MulticastLock? = null
            try {
                // ACQUIRE MULTICAST LOCK SO ANDROID ALLOWS INCOMING SSDP PACKETS!
                val wifiManager = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
                multicastLock = wifiManager.createMulticastLock("UPnP_Multicast_Lock")
                multicastLock.setReferenceCounted(true)
                multicastLock.acquire()

                Log.d(TAG, "Starting UPnP discovery with Multicast Lock...")
                val discover = GatewayDiscover()
                
                var device: GatewayDevice? = null
                for (i in 1..maxAttempts) {
                    discover.discover()
                    device = discover.validGateway
                    if (device != null) break
                    Log.d(TAG, "UPnP gateway not found, retrying... ($i/$maxAttempts)")
                    Thread.sleep(1000)
                }

                if (device != null) {
                    val localAddress = device.localAddress
                    Log.d(TAG, "Found UPnP Gateway: ${device.friendlyName}")
                    
                    val mappingEntry = PortMappingEntry()
                    val isMapped = device.getSpecificPortMappingEntry(port, "TCP", mappingEntry)
                    
                    if (isMapped) {
                        Log.d(TAG, "Port $port is already mapped on the router!")
                        activeDevice = device
                        activePort = port
                    } else {
                        Log.d(TAG, "Attempting to map port $port (TCP) to ${localAddress.hostAddress}...")
                        val success = device.addPortMapping(port, port, localAddress.hostAddress, "TCP", "P2PDroidRemote_TCP")
                        if (success) {
                            Log.d(TAG, "✅ UPnP Port Mapping SUCCESS! Router public port $port is now open.")
                            activeDevice = device
                            activePort = port
                        } else {
                            Log.e(TAG, "❌ UPnP Port Mapping FAILED.")
                        }
                    }
                } else {
                    Log.e(TAG, "❌ UPnP Discovery FAILED.")
                }
            } catch (e: Exception) {
                Log.e(TAG, "UPnP Exception: ${e.message}", e)
            } finally {
                if (multicastLock != null && multicastLock.isHeld) {
                    multicastLock.release()
                }
            }
        }
    }

    fun closeActivePort() {
        thread(name = "UPnP-Cleanup") {
            try {
                if (activeDevice != null && activePort > 0) {
                    Log.d(TAG, "Removing UPnP mapping for port $activePort...")
                    val success = activeDevice!!.deletePortMapping(activePort, "TCP")
                    activeDevice = null
                    activePort = -1
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error closing UPnP port: ${e.message}")
            }
        }
    }
}
"""
with open(upnp_file, 'w', encoding='utf-8') as f:
    f.write(new_upnp_content)

# 2. Update DataTransferClient.kt to pass Context
dt_file = r'D:\SOFT\Coder\Android\app\src\main\java\com\example\p2pdroidremote\DataTransferClient.kt'
with open(dt_file, 'r', encoding='utf-8') as f:
    dt_content = f.read()

# Replace UPnPManager.openPortBackground(port) with UPnPManager.openPortBackground(context, port)
dt_content = dt_content.replace("UPnPManager.openPortBackground(port)", "UPnPManager.openPortBackground(context, port)")

with open(dt_file, 'w', encoding='utf-8') as f:
    f.write(dt_content)