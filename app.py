import os
import time
import socket
import json
import uuid
import threading
from werkzeug.utils import secure_filename
from flask import Flask, render_template_string, request, jsonify, send_from_directory

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def cleanup_uploads():
    """Background thread to clean up old uploads"""
    while True:
        try:
            now = time.time()
            files_to_remove = []
            for filename in os.listdir(UPLOAD_FOLDER):
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.isfile(filepath):
                    # Remove files older than 30 minutes
                    if now - os.path.getmtime(filepath) > 1800:
                        files_to_remove.append((filepath, filename.split('_')[0]))

            with state_lock:
                for filepath, file_id in files_to_remove:
                    try:
                        if os.path.exists(filepath):
                            os.remove(filepath)
                        if file_id in state["files"]:
                            del state["files"][file_id]
                    except Exception as ex:
                        print(f"Error removing {filepath}: {ex}")
        except Exception as e:
            print(f"Cleanup error: {e}")
        time.sleep(300) # Run every 5 minutes

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

LOCAL_IP = get_local_ip()
PORT = 5000

# In-memory storage for signaling and presence
state = {
    "devices": {},
    "signals": [], # Each signal: { "sender": ..., "target": ..., "timestamp": ..., ... }
    "files": {}    # Mapping of file_id to metadata
}
state_lock = threading.Lock()

# --- HTML TEMPLATE ---
HTML_TEMPLATE = """
{% raw %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AirShare - Local Transfer</title>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script>window.react = React;</script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide-react@0.477.0/dist/umd/lucide-react.min.js"></script>
    <script>
        // Compatibility shim for different Lucide UMD versions
        window.LucideReact = window.LucideReact || window.lucide;
    </script>
    <script src="https://unpkg.com/dexie/dist/dexie.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/qrcode@1.5.1/build/qrcode.min.js"></script>
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#1e1b4b">
    <link rel="apple-touch-icon" href="https://raw.githubusercontent.com/lucide-react/lucide/main/icons/zap.png">
    <style>
        @keyframes radar {
            0% { transform: scale(0.2); opacity: 1; }
            100% { transform: scale(3.5); opacity: 0; }
        }
        .radar-ring {
            position: absolute; border-radius: 50%; border: 1px solid rgba(255, 255, 255, 0.4);
            box-shadow: 0 0 20px rgba(255, 255, 255, 0.1) inset; animation: radar 4s linear infinite;
        }
        .radar-ring:nth-child(1) { animation-delay: 0s; }
        .radar-ring:nth-child(2) { animation-delay: 1.33s; }
        .radar-ring:nth-child(3) { animation-delay: 2.66s; }

        .glass-panel {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(24px);
            -webkit-backdrop-filter: blur(24px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        }
        .glass-button {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            transition: all 0.3s ease;
        }
        .glass-button:hover {
            background: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.4);
        }

        body {
            background: radial-gradient(circle at 50% 50%, #1e1b4b 0%, #0f172a 100%);
            min-height: 100vh;
            color: white;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }

        .circular-progress {
            transition: stroke-dashoffset 0.35s;
            transform: rotate(-90deg);
            transform-origin: 50% 50%;
        }
        @keyframes celebrate {
            0% { transform: scale(1); opacity: 0.5; }
            50% { transform: scale(1.5); opacity: 1; }
            100% { transform: scale(2); opacity: 0; }
        }
        .celebration-ring {
            position: absolute; border: 2px solid #6366f1; border-radius: 50%;
            animation: celebrate 0.8s ease-out forwards;
        }
    </style>
</head>
<body>
    <div id="root"></div>

    <script type="text/babel">
        const { useState, useEffect, useRef, useCallback } = React;
        const {
            Monitor, Smartphone, Laptop, File, Check, X,
            UploadCloud, Shield, Zap, Image: LucideImage,
            Video, Music, History: LucideHistory, Settings, QrCode,
            Download, Trash2, ShieldCheck, Lock, Info
        } = LucideReact;

        const ImageIcon = LucideImage;

        const MY_ID = Math.random().toString(36).substr(2, 9);

        // Setup Database
        const db = new Dexie("AirShareDB");
        db.version(2).stores({
            history: '++id, name, size, type, timestamp, sender, status, fileId'
        });

        function App() {
            const [myDevice, setMyDevice] = useState(() => {
                const ua = navigator.userAgent;
                let type = /iPhone|iPad|iPod/i.test(ua) ? 'iphone' : /Android/i.test(ua) ? 'smartphone' : 'pc';
                return { uid: MY_ID, name: localStorage.getItem('deviceName') || (type === 'pc' ? 'Host PC' : 'Mobile Device'), type };
            });

            const [peers, setPeers] = useState([]);
            const [selectedFiles, setSelectedFiles] = useState([]);
            const [selectedPeers, setSelectedPeers] = useState([]);
            const [transfers, setTransfers] = useState({});
            const [incomingRequests, setIncomingRequests] = useState([]);
            const [dragActive, setDragActive] = useState(false);
            const [activeTab, setActiveTab] = useState('radar');
            const [history, setHistory] = useState([]);
            const [showQR, setShowQR] = useState(false);
            const [localConfig, setLocalConfig] = useState({ ip: '...', port: 5000 });
            const [securityMode, setSecurityMode] = useState(localStorage.getItem('securityMode') || 'approval');
            const [pin, setPin] = useState(localStorage.getItem('securityPin') || '1234');
            const [showPinEntry, setShowPinEntry] = useState(null);
            const [toasts, setToasts] = useState([]);
            const [celebrations, setCelebrations] = useState([]);
            const [logs, setLogs] = useState([]);

            const stateRef = useRef({ peers, transfers, selectedFiles });
            useEffect(() => {
                stateRef.current = { peers, transfers, selectedFiles };
            }, [peers, transfers, selectedFiles]);

            const addLog = (msg) => {
                console.log(`[AirShare] ${msg}`);
                setLogs(prev => [`${new Date().toLocaleTimeString()} - ${msg}`, ...prev].slice(0, 50));
            };

            useEffect(() => {
                fetch('/api/config').then(res => res.json()).then(setLocalConfig);
                loadHistory();
            }, []);

            const loadHistory = async () => {
                const items = await db.history.orderBy('timestamp').reverse().toArray();
                setHistory(items);
            };

            const syncState = async () => {
                try {
                    const res = await fetch('/api/sync', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ device: myDevice })
                    });
                    const data = await res.json();
                    setPeers(Object.values(data.devices).filter(d => d.uid !== MY_ID));
                    data.signals.forEach(sig => handleSignal(sig));
                } catch (e) { console.error("Sync error", e); }
            };

            const sendSignal = async (target, type, payload) => {
                await fetch('/api/signal', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ sender: MY_ID, senderDevice: myDevice, target, type, payload })
                });
            };

            useEffect(() => {
                const interval = setInterval(syncState, 2000);
                return () => clearInterval(interval);
            }, [myDevice]);

            const handleSignal = async (signal) => {
                const { type, payload, sender, senderDevice } = signal;
                if (type === 'transfer_request') {
                    if (securityMode === 'pin') {
                        setShowPinEntry({ sender, senderDevice, files: payload.files });
                    } else {
                        setIncomingRequests(prev => [...prev, { id: Math.random(), sender, senderDevice, files: payload.files }]);
                    }
                } else if (type === 'transfer_accepted') {
                    startUploading(sender);
                } else if (type === 'transfer_declined') {
                    showToast(`${senderDevice.name} declined the transfer.`);
                } else if (type === 'file_available') {
                    handleIncomingFile(sender, payload);
                }
            };

            const startUploading = async (peerId) => {
                const filesToSend = stateRef.current.selectedFiles;
                if (filesToSend.length === 0) return;

                const totalSize = filesToSend.reduce((acc, f) => acc + f.file.size, 0);
                const fileProgresses = {}; // Map of file id -> bytes loaded
                const fileSpeeds = {};     // Map of file id -> current speed

                setTransfers(prev => ({...prev, [peerId]: {
                    status: 'sending', progress: 0, speed: 0,
                    currentFile: `Uploading ${filesToSend.length} files...`,
                    total: filesToSend.length, current: 0
                }}));

                const uploadPromises = filesToSend.map(async (fObj, index) => {
                    const file = fObj.file;
                    const fileId = fObj.id;

                    const formData = new FormData();
                    formData.append('file', file);
                    formData.append('sender', MY_ID);
                    formData.append('target', peerId);

                    const xhr = new XMLHttpRequest();
                    xhr.open('POST', '/api/upload', true);

                    let startTime = Date.now();

                    xhr.upload.onprogress = (e) => {
                        if (e.lengthComputable) {
                            fileProgresses[fileId] = e.loaded;
                            const elapsed = (Date.now() - startTime) / 1000;
                            fileSpeeds[fileId] = e.loaded / (elapsed || 0.1) / (1024 * 1024);

                            // Aggregate progress
                            const totalLoaded = Object.values(fileProgresses).reduce((acc, val) => acc + val, 0);
                            const totalSpeed = Object.values(fileSpeeds).reduce((acc, val) => acc + val, 0);
                            const overallPercent = Math.round((totalLoaded / totalSize) * 100);

                            setTransfers(prev => ({...prev, [peerId]: {
                                ...prev[peerId],
                                progress: overallPercent,
                                speed: totalSpeed.toFixed(1),
                                current: Object.keys(fileProgresses).length // Not quite right but gives a sense of activity
                            }}));
                        }
                    };

                    const uploadPromise = new Promise((resolve, reject) => {
                        xhr.onload = () => {
                            if (xhr.status === 200) {
                                try {
                                    const response = JSON.parse(xhr.responseText);
                                    resolve(response.file_id);
                                } catch (e) { reject(new Error('Invalid response')); }
                            } else {
                                reject(new Error('Upload failed'));
                            }
                        };
                        xhr.onerror = () => reject(new Error('Upload failed'));
                    });

                    xhr.send(formData);

                    try {
                        const serverFileId = await uploadPromise;
                        sendSignal(peerId, 'file_available', {
                            file_id: serverFileId,
                            name: file.name,
                            size: file.size,
                            type: file.type
                        });

                        await db.history.add({
                            name: file.name, size: file.size, type: file.type,
                            timestamp: Date.now(), sender: 'Me', status: 'sent', fileId: serverFileId
                        });
                    } catch (err) {
                        addLog(`Upload error for ${file.name}: ${err.message}`);
                    }
                });

                try {
                    await Promise.all(uploadPromises);
                } catch (err) {
                    showToast("One or more uploads failed");
                }

                setTransfers(prev => ({...prev, [peerId]: { status: 'complete', progress: 100 }}));
                setCelebrations(prev => [...prev, { id: Date.now(), peerId }]);
                setTimeout(() => setCelebrations(prev => prev.filter(c => c.peerId !== peerId)), 1000);
                setSelectedFiles([]);
                loadHistory();
                notify("Transfer Complete", "Files sent successfully.");
            };

            const handleIncomingFile = async (senderId, fileMeta) => {
                const { file_id, name, size, type } = fileMeta;

                setTransfers(prev => ({...prev, [senderId]: { status: 'receiving', progress: 100, currentFile: name }}));

                const senderName = stateRef.current.peers.find(p => p.uid === senderId)?.name || 'Unknown Device';

                await db.history.add({
                    name, size, type, timestamp: Date.now(),
                    sender: senderName, status: 'received', fileId: file_id
                });

                loadHistory();

                // Trigger download
                const downloadUrl = `/api/download/${file_id}`;
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = name;
                document.body.appendChild(a);
                a.click();
                setTimeout(() => {
                    document.body.removeChild(a);
                    setTransfers(prev => ({...prev, [senderId]: { status: 'complete', progress: 100 }}));
                    setCelebrations(prev => [...prev, { id: Date.now(), peerId: senderId }]);
                    setTimeout(() => setCelebrations(prev => prev.filter(c => c.peerId !== senderId)), 1000);
                }, 100);

                notify("File Received", `${name} has been downloaded.`);
            };

            const showToast = (message, type = 'info') => {
                const id = Math.random().toString(36).substr(2, 9);
                setToasts(prev => [...prev, { id, message, type }]);
                setTimeout(() => {
                    setToasts(prev => prev.filter(t => t.id !== id));
                }, 3000);
            };

            const notify = (title, body) => {
                if (Notification.permission === 'granted') {
                    new Notification(title, { body });
                } else if (Notification.permission !== 'denied') {
                    Notification.requestPermission();
                }
            };

            const formatSize = (bytes) => {
                if (bytes === 0) return '0 B';
                const k = 1024;
                const sizes = ['B', 'KB', 'MB', 'GB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
            };

            const CircularProgress = ({ progress, size = 60 }) => {
                const radius = (size / 2) - 4;
                const circumference = radius * 2 * Math.PI;
                const offset = circumference - (progress / 100) * circumference;
                return (
                    <svg width={size} height={size} className="absolute -inset-2">
                        <circle className="text-white/10" strokeWidth="4" stroke="currentColor" fill="transparent" r={radius} cx={size/2} cy={size/2} />
                        <circle className="text-indigo-500 circular-progress" strokeWidth="4" strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round" stroke="currentColor" fill="transparent" r={radius} cx={size/2} cy={size/2} />
                    </svg>
                );
            };

            const QRCodeModal = () => {
                const canvasRef = useRef();
                useEffect(() => {
                    if (canvasRef.current) {
                        QRCode.toCanvas(canvasRef.current, `http://${localConfig.ip}:${localConfig.port}`, { width: 200, margin: 2 });
                    }
                }, []);
                return (
                    <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-[100]" onClick={() => setShowQR(false)}>
                        <div className="glass-panel p-8 rounded-[2rem] text-center max-w-xs" onClick={e => e.stopPropagation()}>
                            <h2 className="text-xl font-bold mb-4">Connect Device</h2>
                            <p className="text-sm opacity-60 mb-6">Scan to join the network</p>
                            <div className="bg-white p-4 rounded-2xl inline-block mb-6">
                                <canvas ref={canvasRef}></canvas>
                            </div>
                            <div className="text-xs font-mono opacity-50">http://{localConfig.ip}:{localConfig.port}</div>
                        </div>
                    </div>
                );
            };

            const PinModal = () => {
                const [enteredPin, setEnteredPin] = useState('');
                const checkPin = () => {
                    if (enteredPin === pin) {
                        sendSignal(showPinEntry.sender, 'transfer_accepted', {});
                        setShowPinEntry(null);
                    } else {
                        showToast("Incorrect PIN", "error");
                        setEnteredPin('');
                    }
                };
                return (
                    <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-[100]">
                        <div className="glass-panel p-8 rounded-[2rem] text-center w-full max-w-xs">
                            <Lock className="mx-auto mb-4 text-indigo-400" size={48} />
                            <h2 className="text-xl font-bold mb-2">Security Verification</h2>
                            <p className="text-sm opacity-60 mb-6">{showPinEntry.senderDevice.name} wants to send files</p>
                            <input type="password" placeholder="Enter PIN" className="w-full bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-center text-2xl tracking-[1em] mb-4 outline-none focus:border-indigo-500" value={enteredPin} onChange={e => setEnteredPin(e.target.value)} autoFocus />
                            <div className="flex gap-4">
                                <button className="flex-1 py-3 rounded-xl bg-white/10" onClick={() => {sendSignal(showPinEntry.sender, 'transfer_declined', {}); setShowPinEntry(null)}}>Decline</button>
                                <button className="flex-1 py-3 rounded-xl bg-indigo-600 font-bold" onClick={checkPin}>Verify</button>
                            </div>
                        </div>
                    </div>
                );
            }

            return (
                <div className="h-screen flex flex-col" onDragOver={e => {e.preventDefault(); setDragActive(true)}} onDrop={e => {e.preventDefault(); setDragActive(false); setSelectedFiles(Array.from(e.dataTransfer.files).map(f => ({file: f, id: Math.random()})))}}>
                    <header className="px-8 py-6 flex justify-between items-center z-10">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-500/30">
                                <Zap size={24} fill="white" />
                            </div>
                            <h1 className="text-2xl font-black tracking-tight">AirShare Py</h1>
                        </div>
                        <div className="flex gap-2">
                            <button onClick={() => setShowQR(true)} className="glass-button p-3 rounded-full"><QrCode size={20}/></button>
                            <button onClick={() => setActiveTab('history')} className={`glass-button p-3 rounded-full ${activeTab === 'history' ? 'bg-white/20' : ''}`}><LucideHistory size={20}/></button>
                            <button onClick={() => setActiveTab('settings')} className={`glass-button p-3 rounded-full ${activeTab === 'settings' ? 'bg-white/20' : ''}`}><Settings size={20}/></button>
                        </div>
                    </header>

                    <main className="flex-1 relative flex flex-col items-center justify-between p-4 md:p-8 overflow-hidden">
                        {activeTab === 'radar' && (
                            <>
                                <div className="flex-1 flex items-center justify-center w-full min-h-0 relative">
                                    <div className="relative w-full max-w-md lg:max-w-xl aspect-square flex items-center justify-center">
                                        <div className="radar-ring w-32 h-32 md:w-48 md:h-48"></div>
                                        <div className="radar-ring w-64 h-64 md:w-96 md:h-96"></div>
                                        <div className="radar-ring w-96 h-96 md:w-[32rem] md:h-[32rem]"></div>
                                        <div className="relative z-10 glass-panel p-6 md:p-8 rounded-full border-indigo-500/50 border-2 shadow-2xl shadow-indigo-500/20">
                                             {myDevice.type === 'pc' ? <Monitor size={48} className="text-indigo-400"/> : <Smartphone size={48} className="text-indigo-400"/>}
                                        </div>
                                        {peers.map((p, i) => {
                                        const angle = (i * (360 / Math.max(peers.length, 1))) * (Math.PI / 180);
                                        const radius = 180;
                                        const x = Math.cos(angle) * radius;
                                        const y = Math.sin(angle) * radius;
                                        const transfer = transfers[p.uid];
                                        const isPeerSelected = selectedPeers.includes(p.uid);
                                        return (
                                            <div key={p.uid} className="absolute cursor-pointer group transition-all duration-500" style={{transform: `translate(${x}px, ${y}px)`}} onClick={() => {
                                                if (selectedPeers.includes(p.uid)) { setSelectedPeers(prev => prev.filter(id => id !== p.uid)); }
                                                else { setSelectedPeers(prev => [...prev, p.uid]); }
                                            }}>
                                                <div className={`p-5 rounded-full glass-panel border-2 transition-all duration-300 group-hover:scale-110 relative ${isPeerSelected ? 'border-indigo-400 shadow-[0_0_20px_rgba(99,102,241,0.4)]' : 'border-white/10'} ${transfer?.status === 'sending' ? 'animate-pulse' : ''}`}>
                                                    {transfer?.progress > 0 && transfer.progress < 100 && <CircularProgress progress={transfer.progress} size={84} />}
                                                    {p.type === 'pc' ? <Monitor className={isPeerSelected ? 'text-indigo-400' : ''} /> : <Smartphone className={isPeerSelected ? 'text-indigo-400' : ''} />}
                                                    {isPeerSelected && <div className="absolute -top-1 -right-1 bg-indigo-500 rounded-full p-1"><Check size={10} /></div>}
                                                    {celebrations.some(c => c.peerId === p.uid) && <div className="celebration-ring inset-0" />}
                                                </div>
                                                <div className="absolute top-20 left-1/2 -translate-x-1/2 whitespace-nowrap flex flex-col items-center gap-1">
                                                    <div className={`bg-black/40 backdrop-blur-md px-3 py-1 rounded-full text-xs font-medium border ${isPeerSelected ? 'border-indigo-500 text-indigo-400' : 'border-white/10'}`}>
                                                        {p.name} {transfer?.speed && `· ${transfer.speed}MB/s`}
                                                    </div>
                                                    {transfer?.status === 'sending' && transfer.total > 1 && (
                                                        <div className="text-[10px] bg-indigo-600/50 px-2 py-0.5 rounded-full border border-indigo-400/30">
                                                            {transfer.current}/{transfer.total}: {transfer.currentFile}
                                                        </div>
                                                    )}
                                                    {transfer?.status === 'receiving' && (
                                                        <div className="text-[10px] bg-green-600/50 px-2 py-0.5 rounded-full border border-green-400/30">
                                                            Receiving: {transfer.currentFile}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                        })}
                                    </div>
                                </div>
                                <div className={`w-full max-w-md glass-panel p-6 md:p-8 rounded-[2.5rem] transition-all duration-300 relative overflow-hidden group ${dragActive ? 'scale-105 border-indigo-500 ring-4 ring-indigo-500/20' : ''}`}>
                                    {selectedFiles.length === 0 ? (
                                        <div className="text-center relative">
                                            <div className="w-12 h-12 md:w-16 md:h-16 bg-white/5 rounded-2xl flex items-center justify-center mx-auto mb-4 group-hover:bg-indigo-500/20 transition-colors">
                                                <UploadCloud className="text-indigo-400" />
                                            </div>
                                            <div className="text-lg font-bold mb-1">Ready to share?</div>
                                            <div className="text-sm opacity-50 mb-4">Drag files here or</div>
                                            <div className="relative inline-block">
                                                <button className="bg-indigo-600 hover:bg-indigo-500 px-6 py-2 rounded-xl text-sm font-bold transition-all shadow-lg shadow-indigo-500/20">Select Files</button>
                                                <input type="file" multiple className="absolute inset-0 opacity-0 cursor-pointer w-full h-full" onChange={e => setSelectedFiles(Array.from(e.target.files).map(f => ({file: f, id: Math.random()}))) } />
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="flex flex-col gap-3">
                                            <div className="flex justify-between items-center mb-2">
                                                <div className="text-xs font-bold uppercase tracking-widest opacity-40">Queue ({selectedFiles.length})</div>
                                                <button onClick={() => setSelectedFiles([])} className="text-xs text-red-400 hover:underline">Clear</button>
                                            </div>
                                            <div className="max-h-48 overflow-y-auto no-scrollbar flex flex-col gap-2">
                                                {selectedFiles.map(f => (
                                                    <div key={f.id} className="flex items-center gap-3 bg-white/5 p-3 rounded-xl border border-white/5">
                                                        <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center flex-shrink-0">
                                                            {f.file.type.startsWith('image/') ? <ImageIcon size={16} className="text-indigo-400"/> : f.file.type.startsWith('video/') ? <Video size={16} className="text-indigo-400"/> : <File size={16} className="text-indigo-400"/>}
                                                        </div>
                                                        <div className="flex-1 min-w-0">
                                                            <div className="text-sm font-medium truncate">{f.file.name}</div>
                                                            <div className="text-[10px] opacity-40 uppercase">{formatSize(f.file.size)}</div>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                            <button className={`mt-4 w-full py-3 rounded-2xl font-bold transition-all ${selectedPeers.length > 0 ? 'bg-indigo-600 hover:bg-indigo-500' : 'bg-white/5 opacity-50 cursor-not-allowed'}`} disabled={selectedPeers.length === 0} onClick={() => {
                                                selectedPeers.forEach(peerId => { sendSignal(peerId, 'transfer_request', {files: selectedFiles.map(f => f.file.name)}); });
                                                showToast(`Requests sent...`);
                                                setSelectedPeers([]);
                                            }}>SEND TO {selectedPeers.length} DEVICE{selectedPeers.length !== 1 ? 'S' : ''}</button>
                                        </div>
                                    )}
                                </div>
                            </>
                        )}

                        {activeTab === 'history' && (
                            <div className="w-full max-w-2xl h-full flex flex-col py-4">
                                <div className="flex justify-between items-center mb-6">
                                    <h2 className="text-2xl font-bold flex items-center gap-3"><LucideHistory className="text-indigo-400" /> History</h2>
                                    <button onClick={() => setActiveTab('radar')} className="glass-button px-4 py-2 rounded-xl text-sm font-bold">Back</button>
                                </div>
                                <div className="flex-1 overflow-y-auto pr-2 no-scrollbar flex flex-col gap-3">
                                    {history.length === 0 ? (
                                        <div className="h-full flex flex-col items-center justify-center opacity-30"><File size={64} className="mb-4" /><p>No transfers yet</p></div>
                                    ) : (
                                        history.map(item => (
                                            <div key={item.id} className="glass-panel p-4 rounded-2xl flex items-center gap-4 group">
                                                <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center relative">
                                                    {item.type?.startsWith('image/') ? <ImageIcon /> : item.type?.startsWith('video/') ? <Video /> : <File />}
                                                    <div className={`absolute -top-1 -right-1 w-4 h-4 rounded-full flex items-center justify-center text-[8px] ${item.status === 'received' ? 'bg-green-500' : 'bg-blue-500'}`}>
                                                        {item.status === 'received' ? <Download size={8} /> : <UploadCloud size={8} />}
                                                    </div>
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="font-bold truncate text-sm">{item.name}</div>
                                                    <div className="text-xs opacity-50">{formatSize(item.size)} • {item.sender} • {new Date(item.timestamp).toLocaleTimeString()}</div>
                                                </div>
                                                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                    {item.status === 'received' && item.fileId && (
                                                        <a href={`/api/download/${item.fileId}`} download={item.name} className="p-3 bg-white/5 rounded-xl hover:bg-indigo-500/20">
                                                            <Download size={18} className="text-indigo-400" />
                                                        </a>
                                                    )}
                                                    <button onClick={() => db.history.delete(item.id).then(loadHistory)} className="p-3 bg-white/5 rounded-xl hover:bg-red-500/20"><Trash2 size={18} className="text-red-400" /></button>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </div>
                        )}

                        {activeTab === 'settings' && (
                            <div className="w-full max-w-md py-4">
                                <div className="flex justify-between items-center mb-8">
                                    <h2 className="text-2xl font-bold flex items-center gap-3"><Settings className="text-indigo-400" /> Settings</h2>
                                    <button onClick={() => setActiveTab('radar')} className="glass-button px-4 py-2 rounded-xl text-sm font-bold">Done</button>
                                </div>
                                <div className="space-y-6">
                                    <div className="glass-panel p-6 rounded-3xl">
                                        <label className="block text-xs font-bold uppercase opacity-40 mb-3 tracking-widest">Device Name</label>
                                        <input type="text" className="w-full bg-white/5 border border-white/10 rounded-2xl px-4 py-3 outline-none focus:border-indigo-500 transition-colors" value={myDevice.name} onChange={e => { setMyDevice({...myDevice, name: e.target.value}); localStorage.setItem('deviceName', e.target.value); }} />
                                    </div>
                                    <div className="glass-panel p-6 rounded-3xl">
                                        <label className="block text-xs font-bold uppercase opacity-40 mb-4 tracking-widest">Security Mode</label>
                                        <div className="flex gap-2">
                                            <button className={`flex-1 py-4 rounded-2xl flex flex-col items-center gap-2 transition-all ${securityMode === 'approval' ? 'bg-indigo-600 shadow-lg shadow-indigo-500/20' : 'bg-white/5'}`} onClick={() => {setSecurityMode('approval'); localStorage.setItem('securityMode', 'approval')}}><ShieldCheck size={24} /><span className="text-sm font-bold">Approval</span></button>
                                            <button className={`flex-1 py-4 rounded-2xl flex flex-col items-center gap-2 transition-all ${securityMode === 'pin' ? 'bg-indigo-600 shadow-lg shadow-indigo-500/20' : 'bg-white/5'}`} onClick={() => {setSecurityMode('pin'); localStorage.setItem('securityMode', 'pin')}}><Lock size={24} /><span className="text-sm font-bold">PIN Code</span></button>
                                        </div>
                                        {securityMode === 'pin' && (
                                            <div className="mt-4 animate-in fade-in slide-in-from-top-2">
                                                <input type="text" className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-center font-mono tracking-widest outline-none focus:border-indigo-500" value={pin} maxLength={4} onChange={e => { const v = e.target.value.replace(/[^0-9]/g, ''); setPin(v); localStorage.setItem('securityPin', v); }} />
                                            </div>
                                        )}
                                    </div>
                                    <div className="glass-panel p-6 rounded-3xl flex items-center gap-4 border-indigo-500/30">
                                        <Info className="text-indigo-400" />
                                        <div className="text-xs opacity-60">HTTP Mode: Browser security may limit some PWA features.</div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </main>

                    <div className="fixed bottom-12 left-1/2 -translate-x-1/2 z-[200] flex flex-col gap-3 w-full max-w-xs pointer-events-none">
                        {toasts.map(t => (
                            <div key={t.id} className="glass-panel px-6 py-4 rounded-[1.5rem] flex items-center gap-4 animate-in slide-in-from-bottom-8 fade-in duration-500 pointer-events-auto shadow-2xl">
                                <div className={`w-3 h-3 rounded-full ${t.type === 'error' ? 'bg-red-500 shadow-[0_0_12px_rgba(239,68,68,0.5)]' : 'bg-indigo-500 shadow-[0_0_12px_rgba(99,102,241,0.5)]'}`} />
                                <span className="text-sm font-bold tracking-tight">{t.message}</span>
                            </div>
                        ))}
                    </div>

                    {showQR && <QRCodeModal />}
                    {showPinEntry && <PinModal />}
                    {incomingRequests.map(req => (
                        <div key={req.id} className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-[100]">
                            <div className="glass-panel p-10 rounded-[2.5rem] max-w-xs w-full text-center">
                                <div className="w-20 h-20 bg-indigo-600/20 rounded-full flex items-center justify-center mx-auto mb-6"><Smartphone className="text-indigo-400" size={40} /></div>
                                <h2 className="text-xl font-bold mb-2">{req.senderDevice.name}</h2>
                                <p className="text-sm opacity-60 mb-8">Wants to share {req.files.length} file{req.files.length > 1 ? 's' : ''}</p>
                                <div className="flex gap-4">
                                    <button className="flex-1 py-4 rounded-2xl bg-white/5 font-bold hover:bg-white/10" onClick={() => { sendSignal(req.sender, 'transfer_declined', {}); setIncomingRequests(prev => prev.filter(r => r.id !== req.id)); }}>Decline</button>
                                    <button className="flex-1 py-4 rounded-2xl bg-indigo-600 font-bold hover:bg-indigo-500 shadow-lg shadow-indigo-500/20" onClick={() => { sendSignal(req.sender, 'transfer_accepted', {}); setIncomingRequests(prev => prev.filter(r => r.id !== req.id)); }}>Accept</button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            );
        }

        const root = ReactDOM.createRoot(document.getElementById('root'));
        root.render(<App />);

        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js');
        }
    </script>
</body>
</html>
{% endraw %}
"""

# --- ROUTES ---

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "AirShare Py",
        "short_name": "AirShare",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#1e1b4b",
        "icons": [
            {
                "src": "https://raw.githubusercontent.com/lucide-react/lucide/main/icons/zap.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    })

@app.route('/api/config')
def get_config():
    return jsonify({
        "ip": LOCAL_IP,
        "port": PORT
    })

@app.route('/sw.js')
def service_worker():
    sw_code = """
    const CACHE_NAME = 'airshare-v2';
    const ASSETS = [
        '/',
        'https://unpkg.com/react@18/umd/react.production.min.js',
        'https://unpkg.com/react-dom@18/umd/react-dom.production.min.js',
        'https://unpkg.com/@babel/standalone/babel.min.js',
        'https://cdn.tailwindcss.com',
        'https://unpkg.com/lucide-react@0.477.0/dist/umd/lucide-react.min.js',
        'https://unpkg.com/dexie/dist/dexie.js',
        'https://cdn.jsdelivr.net/npm/qrcode@1.5.1/build/qrcode.min.js',
        'https://raw.githubusercontent.com/lucide-react/lucide/main/icons/zap.png'
    ];

    self.addEventListener('install', (e) => {
        e.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS)));
        self.skipWaiting();
    });

    self.addEventListener('activate', (e) => {
        e.waitUntil(caches.keys().then(keys => Promise.all(keys.map(key => { if (key !== CACHE_NAME) return caches.delete(key); }))));
    });

    self.addEventListener('fetch', (e) => {
        if (e.request.method !== 'GET' || e.request.url.includes('/api/')) return e.respondWith(fetch(e.request));
        e.respondWith(caches.match(e.request).then(response => {
            return response || fetch(e.request).then(fetchRes => {
                return caches.open(CACHE_NAME).then(cache => {
                    cache.put(e.request.url, fetchRes.clone());
                    return fetchRes;
                });
            });
        }).catch(() => caches.match('/')));
    });
    """
    return sw_code, 200, {'Content-Type': 'application/javascript'}

@app.route('/api/sync', methods=['POST'])
def sync():
    data = request.json
    device = data.get('device')
    uid = device.get('uid')
    now = time.time()
    with state_lock:
        state["devices"][uid] = {**device, "last_seen": now}
        state["devices"] = {k: v for k, v in state["devices"].items() if now - v["last_seen"] < 10}
        state["signals"] = [s for s in state["signals"] if now - s.get("timestamp", 0) < 30]
        my_signals = [s for s in state["signals"] if s["target"] == uid]
        state["signals"] = [s for s in state["signals"] if s["target"] != uid]
    return jsonify({ "devices": state["devices"], "signals": my_signals })

@app.route('/api/signal', methods=['POST'])
def signal():
    signal_data = request.json
    signal_data["timestamp"] = time.time()
    with state_lock:
        state["signals"].append(signal_data)
    return jsonify({"status": "ok"})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    safe_name = secure_filename(file.filename)
    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{safe_name}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    with state_lock:
        state["files"][file_id] = {
            "filename": safe_name,
            "internal_path": filename,
            "timestamp": time.time()
        }

    return jsonify({"file_id": file_id})

@app.route('/api/download/<file_id>')
def download_file(file_id):
    with state_lock:
        file_meta = state["files"].get(file_id)
    if not file_meta:
        return "File not found", 404

    return send_from_directory(UPLOAD_FOLDER, file_meta["internal_path"], as_attachment=True, download_name=file_meta["filename"])

if __name__ == '__main__':
    # Start cleanup thread
    threading.Thread(target=cleanup_uploads, daemon=True).start()

    print(f"AirShare Py running at http://{LOCAL_IP}:{PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=True)
