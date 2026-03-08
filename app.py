import os
import time
import socket
import json
import uuid
import threading
from werkzeug.utils import secure_filename
from flask import Flask, render_template_string, request, jsonify, send_from_directory, Response

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
        time.sleep(300)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

LOCAL_IP = get_local_ip()
PORT = 5000

state = {
    "devices": {},
    "signals": [],
    "files": {},
    "clients": {}
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
        window.LucideReact = window.LucideReact || window.lucide;
    </script>
    <script src="https://unpkg.com/dexie/dist/dexie.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/qrcode@1.5.1/build/qrcode.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#1e1b4b">
    <link rel="apple-touch-icon" href="https://raw.githubusercontent.com/lucide-react/lucide/main/icons/zap.png">
    <style>
        :root {
            --accent-primary: #007aff;
            --accent-glow: rgba(0, 122, 255, 0.3);
            --bg-color: #000000;
            --text-color: #ffffff;
            --panel-bg: rgba(30, 30, 30, 0.6);
            --panel-border: rgba(255, 255, 255, 0.15);
            --glass-blur: blur(40px);
            --card-radius: 2rem;
        }
        body.theme-light {
            --accent-primary: #007aff;
            --accent-glow: rgba(0, 122, 255, 0.2);
            --bg-color: #f2f2f7;
            --text-color: #000000;
            --panel-bg: rgba(255, 255, 255, 0.7);
            --panel-border: rgba(0, 0, 0, 0.08);
        }
        @keyframes float {
            0%, 100% { transform: translateY(0) scale(1); }
            50% { transform: translateY(-20px) scale(1.05); }
        }
        .liquid-bg {
            position: fixed; inset: 0; z-index: -1; overflow: hidden; background: var(--bg-color);
        }
        .blob {
            position: absolute; border-radius: 50%; filter: blur(80px); opacity: 0.4;
            animation: float 20s ease-in-out infinite;
        }
        .blob-1 { width: 600px; height: 600px; background: #5856d6; top: -10%; left: -10%; animation-delay: 0s; }
        .blob-2 { width: 500px; height: 500px; background: #007aff; bottom: -5%; right: -5%; animation-delay: -5s; }
        .blob-3 { width: 400px; height: 400px; background: #af52de; top: 40%; left: 30%; animation-delay: -10s; }

        @keyframes radar-pulse {
            0% { transform: scale(0.6); opacity: 0.6; stroke-width: 1px; }
            100% { transform: scale(2.5); opacity: 0; stroke-width: 0.5px; }
        }
        .radar-circle {
            fill: none; stroke: var(--text-color); opacity: 0.1;
            transform-origin: center; animation: radar-pulse 6s cubic-bezier(0.2, 0.8, 0.2, 1) infinite;
            pointer-events: none;
        }
        .radar-circle:nth-child(2) { animation-delay: 2s; }
        .radar-circle:nth-child(3) { animation-delay: 4s; }

        .glass-panel {
            background: var(--panel-bg);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border: 0.5px solid var(--panel-border);
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
        }
        .glass-button {
            background: rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(10px);
            border: 0.5px solid rgba(255, 255, 255, 0.1);
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .theme-light .glass-button { background: rgba(0, 0, 0, 0.04); border-color: rgba(0, 0, 0, 0.08); }
        .glass-button:active { transform: scale(0.92); opacity: 0.8; }

        .drag-overlay {
            background: rgba(0, 122, 255, 0.05);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 2px solid var(--accent-primary);
        }
        body {
            min-height: 100vh;
            color: var(--text-color);
            overflow: hidden;
            transition: background 0.8s ease, color 0.8s ease;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
            -webkit-font-smoothing: antialiased;
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
            position: absolute; border: 2px solid var(--accent-primary); border-radius: 50%;
            animation: celebrate 0.8s ease-out forwards;
        }
        @keyframes pulse-beam {
            0% { stroke-dashoffset: 200; opacity: 0.3; stroke-width: 1; }
            50% { opacity: 1; stroke-width: 3; }
            100% { stroke-dashoffset: 0; opacity: 0.3; stroke-width: 1; }
        }
        .energy-beam {
            stroke: var(--accent-primary);
            stroke-dasharray: 15 10;
            filter: drop-shadow(0 0 12px var(--accent-glow));
            animation: pulse-beam 1.5s linear infinite;
        }
        .drop-glow {
            box-shadow: 0 0 30px var(--accent-glow);
            border-color: var(--accent-primary) !important;
        }
        @keyframes ambient-glow {
            0%, 100% { box-shadow: 0 0 15px var(--accent-glow); border-color: var(--panel-border); }
            50% { box-shadow: 0 0 30px var(--accent-glow); border-color: var(--accent-primary); }
        }
        .ambient-glow {
            animation: ambient-glow 3s ease-in-out infinite;
        }
    </style>
</head>
<body>
    <div id="root"></div>

    <script type="text/babel">
        const { useState, useEffect, useRef, useCallback, useMemo } = React;
        const {
            File, Check, X, UploadCloud, Shield, Zap, Image: LucideImage,
            Video, Music, History: LucideHistory, Settings, QrCode,
            Download, Trash2, ShieldCheck, Lock, Info, Pause, Play,
            MoreVertical, User, Star, Battery, BatteryCharging, BatteryLow, BatteryMedium, BatteryWarning,
            Copy, ExternalLink, Wifi, WifiOff, SignalHigh, SignalMedium, SignalLow, RefreshCcw,
            ChevronRight, Share, Smartphone, Monitor, Laptop
        } = LucideReact;

        const ImageIcon = LucideImage;
        const MY_ID = Math.random().toString(36).substr(2, 9);
        const CHUNK_SIZE = 1024 * 1024; // 1MB chunks

        function FilePreview({ file, full = false }) {
            const [url, setUrl] = useState(null);
            useEffect(() => {
                if (file.type.startsWith('image/') || file.type.startsWith('video/') || file.type.startsWith('audio/')) {
                    const u = URL.createObjectURL(file);
                    setUrl(u);
                    return () => URL.revokeObjectURL(u);
                }
            }, [file]);

            if (file.type.startsWith('image/') && url) return <img src={url} className={`w-full h-full object-cover ${full ? 'rounded-2xl' : ''}`} />;
            if (file.type.startsWith('video/') && url) return <video src={url} controls={full} className={`w-full h-full object-cover ${full ? 'rounded-2xl' : ''}`} />;
            if (file.type.startsWith('audio/') && url) return <div className="w-full h-full flex flex-col items-center justify-center bg-white/5"><Music size={full ? 48 : 24} className="mb-2 text-indigo-400" /><audio src={url} controls={full} className="w-full" /></div>;

            return (
                <div className="w-full h-full flex flex-col items-center justify-center bg-white/5">
                    <File size={full ? 48 : 24} className="text-indigo-400" />
                    {full && <div className="mt-4 text-sm font-bold opacity-60 uppercase">{file.name.split('.').pop()} FILE</div>}
                </div>
            );
        }

        const db = new Dexie("AirShareDB");
        db.version(3).stores({
            history: '++id, name, size, type, timestamp, sender, status, fileId',
            peers: 'uid, nickname, isTrusted'
        });

        function App() {
            const [myDevice, setMyDevice] = useState(() => {
                const ua = navigator.userAgent;
                let os = 'Unknown';
                if (/Windows/i.test(ua)) os = 'Windows';
                else if (/Macintosh/i.test(ua)) os = 'macOS';
                else if (/iPhone|iPad|iPod/i.test(ua)) os = 'iOS';
                else if (/Android/i.test(ua)) os = 'Android';
                else if (/Linux/i.test(ua)) os = 'Linux';
                let type = (os === 'iOS' || os === 'Android') ? 'mobile' : 'pc';
                return {
                    uid: MY_ID,
                    name: localStorage.getItem('deviceName') || `${os} ${type === 'pc' ? 'PC' : 'Mobile'}`,
                    type,
                    os,
                    battery: null
                };
            });

            const [peers, setPeers] = useState([]);
            const [peerCustomizations, setPeerCustomizations] = useState({});
            const [selectedFiles, setSelectedFiles] = useState([]);
            const [selectedPeers, setSelectedPeers] = useState([]);
            const [transfers, setTransfers] = useState({});
            const [pausedPeers, setPausedPeers] = useState([]);
            const [cancelledPeers, setCancelledPeers] = useState([]);
            const [incomingRequests, setIncomingRequests] = useState([]);
            const [dragActive, setDragActive] = useState(false);
            const [activeTab, setActiveTab] = useState('radar');
            const [history, setHistory] = useState([]);
            const [showQR, setShowQR] = useState(false);
            const [localConfig, setLocalConfig] = useState({ ip: '...', port: 5000 });
            const [selectedPreview, setSelectedPreview] = useState(null);
            const [selectedPeerDetails, setSelectedPeerDetails] = useState(null);
            const [securityMode, setSecurityMode] = useState(localStorage.getItem('securityMode') || 'approval');
            const [pin, setPin] = useState(localStorage.getItem('securityPin') || '1234');
            const [showPinEntry, setShowPinEntry] = useState(null);
            const [toasts, setToasts] = useState([]);
            const [celebrations, setCelebrations] = useState([]);
            const [logs, setLogs] = useState([]);
            const [theme, setTheme] = useState(localStorage.getItem('theme') || 'default');

            const stateRef = useRef({ peers, transfers, selectedFiles, pausedPeers, cancelledPeers });
            useEffect(() => {
                stateRef.current = { peers, transfers, selectedFiles, pausedPeers, cancelledPeers };
            }, [peers, transfers, selectedFiles, pausedPeers, cancelledPeers]);

            const addLog = (msg) => {
                console.log(`[AirShare] ${msg}`);
                setLogs(prev => [`${new Date().toLocaleTimeString()} - ${msg}`, ...prev].slice(0, 50));
            };

            useEffect(() => {
                fetch('/api/config').then(res => res.json()).then(setLocalConfig);
                loadHistory();
                if ('getBattery' in navigator) {
                    navigator.getBattery().then(battery => {
                        const updateBattery = () => {
                            setMyDevice(prev => ({
                                ...prev,
                                battery: {
                                    level: Math.round(battery.level * 100),
                                    charging: battery.charging
                                }
                            }));
                        };
                        updateBattery();
                        battery.addEventListener('levelchange', updateBattery);
                        battery.addEventListener('chargingchange', updateBattery);
                    });
                }
                const handleBeforeUnload = (e) => {
                    const hasActiveTransfers = Object.values(stateRef.current.transfers).some(t => t.status === 'sending' || t.status === 'receiving');
                    if (hasActiveTransfers) { e.preventDefault(); e.returnValue = ''; }
                };
                window.addEventListener('beforeunload', handleBeforeUnload);
                let wakeLock = null;
                const requestWakeLock = async () => {
                    try { if ('wakeLock' in navigator) wakeLock = await navigator.wakeLock.request('screen'); } catch (err) {}
                };
                requestWakeLock();
                return () => {
                    window.removeEventListener('beforeunload', handleBeforeUnload);
                    if (wakeLock) wakeLock.release();
                };
            }, []);

            useEffect(() => {
                document.body.className = theme === 'default' ? '' : `theme-${theme}`;
                localStorage.setItem('theme', theme);
            }, [theme]);

            const loadHistory = async () => {
                const items = await db.history.orderBy('timestamp').reverse().toArray();
                setHistory(items);
            };

            const loadPeerCustomizations = async () => {
                const items = await db.peers.toArray();
                const mapping = {};
                items.forEach(p => mapping[p.uid] = p);
                setPeerCustomizations(mapping);
            };

            useEffect(() => { loadPeerCustomizations(); }, []);

            useEffect(() => {
                let eventSource = null;
                const startSSE = () => {
                    eventSource = new EventSource(`/api/events/${MY_ID}`);
                    eventSource.onmessage = (e) => {
                        const data = JSON.parse(e.data);
                        if (data.type === 'sync') { setPeers(Object.values(data.devices).filter(d => d.uid !== MY_ID)); }
                        else if (data.type !== 'heartbeat') { handleSignal(data); }
                    };
                    eventSource.onerror = () => { eventSource.close(); setTimeout(startSSE, 2000); };
                };
                startSSE();
                const syncInterval = setInterval(async () => {
                    const start = Date.now();
                    try {
                        await fetch('/api/sync', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ device: { ...myDevice, rtt: myDevice.lastRtt } })
                        });
                        const rtt = Date.now() - start;
                        setMyDevice(prev => ({ ...prev, lastRtt: rtt }));
                    } catch (e) {}
                }, 3000);
                return () => { if (eventSource) eventSource.close(); clearInterval(syncInterval); };
            }, [myDevice]);

            const sendSignal = async (target, type, payload) => {
                await fetch('/api/signal', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ sender: MY_ID, senderDevice: myDevice, target, type, payload })
                });
            };

            const handleSignal = async (signal) => {
                const { type, payload, sender, senderDevice } = signal;
                if (type === 'transfer_request') {
                    const custom = peerCustomizations[sender];
                    if (custom?.isTrusted) { sendSignal(sender, 'transfer_accepted', {}); return; }
                    if (securityMode === 'pin') { setShowPinEntry({ sender, senderDevice, files: payload.files }); }
                    else { setIncomingRequests(prev => [...prev, { id: Math.random(), sender, senderDevice, files: payload.files }]); }
                } else if (type === 'transfer_accepted') { startUploading(sender); }
                else if (type === 'transfer_declined') { showToast(`${senderDevice.name} declined the transfer.`); }
                else if (type === 'file_available') { handleIncomingFile(sender, payload); }
            };

            const startUploading = async (peerId) => {
                const filesToSend = stateRef.current.selectedFiles;
                if (filesToSend.length === 0) return;
                const totalSize = filesToSend.reduce((acc, f) => acc + f.file.size, 0);
                let totalLoaded = 0;
                let startTime = Date.now();
                setTransfers(prev => ({...prev, [peerId]: { status: 'sending', progress: 0, speed: 0, currentFile: 'Starting...', total: filesToSend.length, current: 0 }}));
                for (let i = 0; i < filesToSend.length; i++) {
                    const fObj = filesToSend[i];
                    const file = fObj.file;
                    const fileId = "f-" + Math.random().toString(36).substr(2, 9);
                    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
                    setTransfers(prev => ({...prev, [peerId]: { ...prev[peerId], current: i + 1, currentFile: file.name }}));
                    for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
                        if (stateRef.current.cancelledPeers?.includes(peerId)) {
                            fetch('/api/cancel_upload', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ file_id: fileId, filename: file.name }) });
                            setTransfers(prev => { const n = {...prev}; delete n[peerId]; return n; });
                            setCancelledPeers(prev => prev.filter(id => id !== peerId));
                            showToast("Transfer cancelled");
                            return;
                        }
                        while (stateRef.current.pausedPeers?.includes(peerId)) {
                            await new Promise(r => setTimeout(r, 500));
                            if (stateRef.current.cancelledPeers?.includes(peerId)) break;
                        }
                        const start = chunkIndex * CHUNK_SIZE;
                        const end = Math.min(start + CHUNK_SIZE, file.size);
                        const chunk = file.slice(start, end);
                        const formData = new FormData();
                        formData.append('file', chunk);
                        formData.append('file_id', fileId);
                        formData.append('chunk_index', chunkIndex);
                        formData.append('total_chunks', totalChunks);
                        formData.append('filename', file.name);
                        try {
                            const res = await fetch('/api/upload', { method: 'POST', body: formData });
                            const result = await res.json();
                            if (result.status === 'complete') {
                                sendSignal(peerId, 'file_available', { file_id: fileId, name: file.name, size: file.size, type: file.type });
                                await db.history.add({ name: file.name, size: file.size, type: file.type, timestamp: Date.now(), sender: 'Me', status: 'sent', fileId: fileId });
                            }
                            totalLoaded += chunk.size;
                            const elapsed = (Date.now() - startTime) / 1000;
                            const speed = totalLoaded / (elapsed || 0.1) / (1024 * 1024);
                            const overallPercent = Math.round((totalLoaded / totalSize) * 100);
                            setTransfers(prev => {
                                const c = prev[peerId] || {};
                                const h = c.speedHistory || [];
                                const nh = [...h, parseFloat(speed.toFixed(1))].slice(-20);
                                return { ...prev, [peerId]: { ...c, progress: overallPercent, speed: speed.toFixed(1), speedHistory: nh } };
                            });
                        } catch (err) { break; }
                    }
                }
                setTransfers(prev => ({...prev, [peerId]: { status: 'complete', progress: 100 }}));
                setCelebrations(prev => [...prev, { id: Date.now(), peerId }]);
                setTimeout(() => setCelebrations(prev => prev.filter(c => c.peerId !== peerId)), 1000);
                confetti({ particleCount: 150, spread: 70, origin: { y: 0.6 }, colors: theme === 'neon' ? ['#00ffcc', '#ffffff'] : ['#6366f1', '#ffffff'] });
                setSelectedFiles([]);
                loadHistory();
                notify("Transfer Complete", "Files sent successfully.");
            };

            const handleIncomingFile = async (senderId, fileMeta) => {
                const { file_id, name, size, type } = fileMeta;
                setTransfers(prev => ({...prev, [senderId]: { status: 'receiving', progress: 100, currentFile: name }}));
                const senderName = stateRef.current.peers.find(p => p.uid === senderId)?.name || 'Unknown Device';
                await db.history.add({ name, size, type, timestamp: Date.now(), sender: senderName, status: 'received', fileId: file_id });
                loadHistory();
                const downloadUrl = `/api/download/${file_id}`;
                const a = document.createElement('a');
                a.href = downloadUrl; a.download = name; document.body.appendChild(a); a.click();
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
                setTimeout(() => { setToasts(prev => prev.filter(t => t.id !== id)); }, 3000);
            };

            const notify = (title, body) => {
                if (Notification.permission === 'granted') { new Notification(title, { body }); }
                else if (Notification.permission !== 'denied') { Notification.requestPermission(); }
            };

            const formatSize = (bytes) => {
                if (bytes === 0) return '0 B';
                const k = 1024, sizes = ['B', 'KB', 'MB', 'GB'], i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
            };

            const SignalIcon = ({ rtt, size = 14 }) => {
                if (rtt === undefined || rtt === null) return <WifiOff size={size} className="opacity-30" />;
                if (rtt < 80) return <div className="flex items-end gap-[1px] h-3"><div className="w-[2px] h-[30%] bg-current opacity-100 rounded-sm"></div><div className="w-[2px] h-[60%] bg-current opacity-100 rounded-sm"></div><div className="w-[2px] h-[100%] bg-current opacity-100 rounded-sm"></div></div>;
                if (rtt < 250) return <div className="flex items-end gap-[1px] h-3"><div className="w-[2px] h-[30%] bg-current opacity-100 rounded-sm"></div><div className="w-[2px] h-[60%] bg-current opacity-100 rounded-sm"></div><div className="w-[2px] h-[100%] bg-current opacity-30 rounded-sm"></div></div>;
                return <div className="flex items-end gap-[1px] h-3"><div className="w-[2px] h-[30%] bg-current opacity-100 rounded-sm"></div><div className="w-[2px] h-[60%] bg-current opacity-30 rounded-sm"></div><div className="w-[2px] h-[100%] bg-current opacity-30 rounded-sm"></div></div>;
            };

            const BatteryIcon = ({ battery, size = 16, className = "" }) => {
                if (!battery) return null;
                const { level, charging } = battery;
                let Icon = Battery;
                if (charging) Icon = BatteryCharging;
                else if (level < 20) Icon = BatteryWarning;
                else if (level < 40) Icon = BatteryLow;
                else if (level < 70) Icon = BatteryMedium;
                return (
                    <div className={`flex items-center gap-1 ${className}`}>
                        <span className="text-[10px] font-bold">{level}%</span>
                        <Icon size={size} className={level < 20 && !charging ? 'text-red-500' : ''} />
                    </div>
                );
            };

            const CircularProgress = ({ progress, size = 60 }) => {
                const radius = (size / 2) - 2, circumference = radius * 2 * Math.PI, offset = circumference - (progress / 100) * circumference;
                return (
                    <svg width={size} height={size} className="absolute -inset-[2px]">
                        <circle className="opacity-10" strokeWidth="2" stroke="currentColor" fill="transparent" r={radius} cx={size/2} cy={size/2} />
                        <circle className="text-[var(--accent-primary)] circular-progress" strokeWidth="2" strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round" stroke="currentColor" fill="transparent" r={radius} cx={size/2} cy={size/2} />
                    </svg>
                );
            };

            const DeviceSilhouette = ({ type, os, className }) => {
                if (os === 'iOS' || type === 'mobile') return (
                    <svg viewBox="0 0 40 80" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
                        <rect x="1" y="1" width="38" height="78" rx="8" stroke="currentColor" strokeWidth="2"/>
                        <rect x="14" y="4" width="12" height="2.5" rx="1.25" fill="currentColor" opacity="0.8"/>
                    </svg>
                );
                if (os === 'macOS' || type === 'pc') return (
                    <svg viewBox="0 0 80 60" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
                        <rect x="5" y="5" width="70" height="42" rx="3" stroke="currentColor" strokeWidth="2"/>
                        <path d="M5 47H75L78 52H2L5 47Z" stroke="currentColor" strokeWidth="2"/>
                        <rect x="35" y="47" width="10" height="2" fill="currentColor" opacity="0.3"/>
                    </svg>
                );
                return <Monitor className={className} />;
            };

            const PeerDetailsModal = ({ peer, custom, onClose }) => {
                const [nickname, setNickname] = useState(custom?.nickname || '');
                const [isTrusted, setIsTrusted] = useState(custom?.isTrusted || false);
                const save = async () => { await db.peers.put({ uid: peer.uid, nickname, isTrusted }); loadPeerCustomizations(); onClose(); };
                return (
                    <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-[110]" onClick={onClose}>
                        <div className="glass-panel p-8 rounded-[2.5rem] w-full max-w-xs" onClick={e => e.stopPropagation()}>
                            <div className="flex justify-center mb-6">
                                <div className="p-6 bg-white/5 rounded-full relative">
                                    {peer.type === 'pc' ? <Monitor size={48} /> : <Smartphone size={48} />}
                                    {isTrusted && <Star className="absolute top-0 right-0 text-yellow-400 fill-yellow-400" size={20} />}
                                </div>
                            </div>
                            <h2 className="text-xl font-bold text-center mb-6">Manage Peer</h2>
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-[10px] font-bold uppercase opacity-40 mb-2 ml-1">Nickname</label>
                                    <input type="text" className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 outline-none focus:border-indigo-500" value={nickname} onChange={e => setNickname(e.target.value)} placeholder={peer.name} />
                                </div>
                                <button className={`w-full py-4 rounded-xl flex items-center justify-center gap-3 transition-all ${isTrusted ? 'bg-yellow-500/20 text-yellow-500 border border-yellow-500/50' : 'bg-white/5 border border-white/10'}`} onClick={() => setIsTrusted(!isTrusted)}>
                                    <Star size={20} className={isTrusted ? 'fill-yellow-500' : ''} />
                                    <span className="font-bold">{isTrusted ? 'Trusted Device' : 'Trust Device'}</span>
                                </button>
                                <div className="pt-4 flex gap-3">
                                    <button className="flex-1 py-3 rounded-xl bg-white/5 font-bold" onClick={onClose}>Cancel</button>
                                    <button className="flex-1 py-3 rounded-xl bg-indigo-600 font-bold" onClick={save}>Save</button>
                                </div>
                            </div>
                        </div>
                    </div>
                );
            };

            const Sparkline = ({ data, width = 40, height = 12 }) => {
                if (!data || data.length < 2) return null;
                const min = Math.min(...data), max = Math.max(...data, 0.1);
                const points = data.map((d, i) => { const x = (i / (data.length - 1)) * width, y = height - ((d - min) / (max - min || 1)) * height; return `${x},${y}`; }).join(' ');
                return <svg width={width} height={height} className="overflow-visible ml-2 inline-block"><polyline fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" points={points} className="opacity-70" /></svg>;
            };

            const EnergyBeam = ({ x, y }) => <svg className="absolute inset-0 w-full h-full pointer-events-none z-0"><line x1="50%" y1="50%" x2={`calc(50% + ${x}px)`} y2={`calc(50% + ${y}px)`} className="energy-beam" /></svg>;

            const QRCodeModal = () => {
                const canvasRef = useRef();
                const url = `http://${localConfig.ip}:${localConfig.port}`;
                useEffect(() => { if (canvasRef.current) QRCode.toCanvas(canvasRef.current, url, { width: 200, margin: 2, color: { dark: '#1e1b4b', light: '#ffffff' } }); }, []);
                const copyUrl = () => { navigator.clipboard.writeText(url); showToast("Link copied to clipboard!"); };
                return (
                    <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-[100]" onClick={() => setShowQR(false)}>
                        <div className="glass-panel p-8 rounded-[2.5rem] text-center max-w-sm w-full mx-4" onClick={e => e.stopPropagation()}>
                            <div className="flex justify-between items-center mb-6">
                                <h2 className="text-xl font-bold">Connect Device</h2>
                                <button onClick={() => setShowQR(false)} className="p-2 hover:bg-white/10 rounded-full transition-colors"><X size={20}/></button>
                            </div>
                            <p className="text-sm opacity-60 mb-8">Scan to join the network or share the link manually</p>
                            <div className="bg-white p-6 rounded-[2rem] inline-block mb-8 shadow-2xl shadow-indigo-500/20"><canvas ref={canvasRef}></canvas></div>
                            <div className="flex flex-col gap-3">
                                <div className="bg-white/5 border border-white/10 rounded-2xl p-4 flex items-center justify-between">
                                    <div className="flex items-center gap-3 overflow-hidden"><ExternalLink size={18} className="text-indigo-400 flex-shrink-0" /><span className="text-xs font-mono truncate opacity-60">{url}</span></div>
                                    <button onClick={copyUrl} className="p-2 hover:bg-white/10 rounded-xl transition-colors text-indigo-400"><Copy size={18} /></button>
                                </div>
                            </div>
                        </div>
                    </div>
                );
            };

            const PinModal = () => {
                const [enteredPin, setEnteredPin] = useState('');
                const checkPin = () => {
                    if (enteredPin === pin) { sendSignal(showPinEntry.sender, 'transfer_accepted', {}); setShowPinEntry(null); }
                    else { showToast("Incorrect PIN", "error"); setEnteredPin(''); }
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
                <div className="h-screen flex flex-col" onDragOver={e => {e.preventDefault(); setDragActive(true)}} onDragLeave={e => { if (e.clientX <= 0 || e.clientY <= 0 || e.clientX >= window.innerWidth || e.clientY >= window.innerHeight) setDragActive(false); }} onDrop={e => {e.preventDefault(); setDragActive(false); setSelectedFiles(Array.from(e.dataTransfer.files).map(f => ({file: f, id: Math.random()})))}}>
                    <div className="liquid-bg">
                        <div className="blob blob-1"></div><div className="blob blob-2"></div><div className="blob blob-3"></div>
                    </div>
                    {dragActive && (
                        <div className="fixed inset-4 z-[300] drag-overlay rounded-[3rem] flex flex-col items-center justify-center pointer-events-none animate-in fade-in zoom-in duration-500">
                            <div className="w-24 h-24 bg-[var(--accent-primary)] rounded-full flex items-center justify-center shadow-2xl shadow-indigo-500/40 mb-8"><UploadCloud size={48} className="text-white" /></div>
                            <h2 className="text-3xl font-bold mb-2">Share to AirShare</h2>
                            <p className="text-lg opacity-60">Drop files to prepare</p>
                        </div>
                    )}
                    <header className="px-8 py-8 flex justify-between items-center z-10">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-[var(--accent-primary)] rounded-[10px] flex items-center justify-center shadow-lg"><Zap size={22} fill="white" stroke="white" /></div>
                            <h1 className="text-2xl font-bold tracking-tight">AirShare</h1>
                        </div>
                        <div className="flex gap-3">
                            <button onClick={() => setShowQR(true)} className="glass-button p-3 rounded-full"><QrCode size={20}/></button>
                            <button onClick={() => setActiveTab('history')} className={`glass-button p-3 rounded-full ${activeTab === 'history' ? 'bg-white/20' : ''}`}><LucideHistory size={20}/></button>
                            <button onClick={() => setActiveTab('settings')} className={`glass-button p-3 rounded-full ${activeTab === 'settings' ? 'bg-white/20' : ''}`}><Settings size={20}/></button>
                        </div>
                    </header>
                    <main className="flex-1 relative flex flex-col items-center justify-between p-4 md:p-8 overflow-hidden">
                        {activeTab === 'radar' && (
                            <>
                                <div className="flex-1 flex items-center justify-center w-full min-h-0 relative">
                                    <div className="relative w-full max-w-lg aspect-square flex items-center justify-center">
                                        <svg className="absolute w-full h-full pointer-events-none overflow-visible">
                                            <circle cx="50%" cy="50%" r="20%" className="radar-circle" />
                                            <circle cx="50%" cy="50%" r="40%" className="radar-circle" />
                                            <circle cx="50%" cy="50%" r="60%" className="radar-circle" />
                                        </svg>
                                        <div className="relative z-10 glass-panel p-8 rounded-full border-white/20 shadow-2xl group active:scale-90 transition-all cursor-pointer overflow-hidden duration-300">
                                             <DeviceSilhouette type={myDevice.type} os={myDevice.os} className="w-14 h-14 text-[var(--accent-primary)]" />
                                             <div className="absolute inset-0 bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                                        </div>
                                        {peers.map((p, i) => {
                                            const angle = (i * (360 / Math.max(peers.length, 1)) - 90) * (Math.PI / 180), radius = 160, x = Math.cos(angle) * radius, y = Math.sin(angle) * radius;
                                            const transfer = transfers[p.uid], isActive = transfer?.status === 'sending' || transfer?.status === 'receiving', isPeerSelected = selectedPeers.includes(p.uid), isPaused = pausedPeers.includes(p.uid);
                                            return (
                                                <React.Fragment key={p.uid}>
                                                    {isActive && <EnergyBeam x={x} y={y} />}
                                                    <div className="absolute cursor-pointer group transition-all duration-700 ease-out animate-in fade-in zoom-in" style={{transform: `translate(${x}px, ${y}px)`}} onClick={() => { if (isActive) return; if (selectedPeers.includes(p.uid)) setSelectedPeers(prev => prev.filter(id => id !== p.uid)); else setSelectedPeers(prev => [...prev, p.uid]); }}>
                                                        <div className={`p-6 rounded-full glass-panel border-white/10 transition-all duration-500 group-hover:scale-110 group-active:scale-90 relative ${isPeerSelected ? 'ring-2 ring-[var(--accent-primary)] shadow-[0_0_30px_var(--accent-glow)]' : ''}`}>
                                                            {transfer?.progress > 0 && transfer.progress < 100 && <CircularProgress progress={transfer.progress} size={88} />}
                                                            <DeviceSilhouette type={p.type} os={p.os} className={`w-10 h-10 ${isPeerSelected ? 'text-[var(--accent-primary)]' : 'opacity-80'}`} />

                                                            <div className="absolute -bottom-2 left-1/2 -translate-x-1/2">
                                                                <div className="bg-black/80 backdrop-blur-md px-1.5 py-0.5 rounded-md border border-white/10 scale-90 flex items-center gap-1 shadow-xl">
                                                                    <SignalIcon rtt={p.rtt} />
                                                                    {p.battery && <BatteryIcon battery={p.battery} size={10} />}
                                                                </div>
                                                            </div>

                                                            {peerCustomizations[p.uid]?.isTrusted && <div className="absolute -top-1 -left-1 bg-yellow-400 rounded-full p-1 shadow-lg"><Star size={8} className="fill-white text-white" /></div>}
                                                            {isPeerSelected && !isActive && <div className="absolute -top-1 -right-1 bg-[var(--accent-primary)] rounded-full p-1"><Check size={8} className="text-white" /></div>}
                                                            {celebrations.some(c => c.peerId === p.uid) && <div className="celebration-ring inset-0" />}
                                                        </div>
                                                        <div className="absolute top-24 left-1/2 -translate-x-1/2 whitespace-nowrap flex flex-col items-center gap-1">
                                                            <div className={`text-xs font-semibold px-2 py-0.5 rounded-full transition-colors ${isPeerSelected ? 'text-[var(--accent-primary)]' : 'opacity-60'}`}>
                                                                {peerCustomizations[p.uid]?.nickname || p.name}
                                                            </div>
                                                            {transfer?.status === 'sending' && (
                                                                <div className="flex flex-col items-center gap-1">
                                                                    <div className="text-[9px] bg-[var(--accent-primary)]/20 text-[var(--accent-primary)] px-2 py-0.5 rounded-full font-bold">{transfer.progress}%</div>
                                                                    <div className="flex items-center text-[8px] opacity-40 font-bold">
                                                                        {transfer.speed} MB/s
                                                                        <Sparkline data={transfer.speedHistory} />
                                                                    </div>
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </React.Fragment>
                                            );
                                        })}
                                    </div>
                                </div>
                                <div className={`w-full max-w-md glass-panel p-6 rounded-[2.5rem] transition-all duration-500 relative overflow-hidden group mb-4 ${dragActive ? 'scale-[1.02]' : ''}`}>
                                    {selectedFiles.length === 0 ? (
                                        <div className="flex items-center gap-4">
                                            <div className="w-14 h-14 bg-white/5 rounded-2xl flex items-center justify-center group-hover:bg-[var(--accent-primary)]/10 transition-colors"><Share className="text-[var(--accent-primary)]" /></div>
                                            <div className="flex-1">
                                                <div className="font-bold">AirShare</div>
                                                <div className="text-sm opacity-50 truncate">Select files or a folder to share</div>
                                            </div>
                                            <div className="flex gap-2 relative">
                                                <div className="relative">
                                                    <button className="bg-[var(--accent-primary)] text-white px-5 py-2.5 rounded-full text-sm font-bold shadow-lg shadow-blue-500/20 active:scale-95 transition-transform">Files</button>
                                                    <input type="file" multiple className="absolute inset-0 opacity-0 cursor-pointer" onChange={e => setSelectedFiles(prev => [...prev, ...Array.from(e.target.files).map(f => ({file: f, id: Math.random()}))]) } />
                                                </div>
                                                <div className="relative">
                                                    <button className="glass-button px-5 py-2.5 rounded-full text-sm font-bold active:scale-95 transition-transform">Folder</button>
                                                    <input type="file" webkitdirectory="" directory="" className="absolute inset-0 opacity-0 cursor-pointer" onChange={e => setSelectedFiles(prev => [...prev, ...Array.from(e.target.files).map(f => ({file: f, id: Math.random()}))]) } />
                                                </div>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="flex flex-col gap-4">
                                            <div className="flex justify-between items-center">
                                                <div className="text-xs font-bold uppercase tracking-widest opacity-30">{selectedFiles.length} item{selectedFiles.length !== 1 ? 's' : ''} to share</div>
                                                <button onClick={() => setSelectedFiles([])} className="text-xs font-bold text-red-500">Cancel</button>
                                            </div>
                                            <div className="flex gap-3 overflow-x-auto pb-2 no-scrollbar">
                                                {selectedFiles.map(f => (
                                                    <div key={f.id} className="flex-shrink-0 w-24 h-24 rounded-2xl bg-black/20 overflow-hidden relative group/card border border-white/5" onClick={() => setSelectedPreview(f.file)}>
                                                        <FilePreview file={f.file} />
                                                        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/card:opacity-100 transition-opacity flex items-center justify-center">
                                                            <button onClick={(e) => { e.stopPropagation(); setSelectedFiles(prev => prev.filter(item => item.id !== f.id)); }} className="bg-red-500 p-1.5 rounded-full"><X size={12}/></button>
                                                        </div>
                                                        <div className="absolute bottom-0 left-0 right-0 p-1.5 bg-gradient-to-t from-black/80 to-transparent">
                                                            <div className="text-[8px] font-bold truncate">{f.file.name}</div>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                            <button className={`w-full py-4 rounded-2xl font-bold transition-all transform active:scale-[0.98] ${selectedPeers.length > 0 ? 'bg-[var(--accent-primary)] text-white' : 'bg-white/5 opacity-50'}`} disabled={selectedPeers.length === 0} onClick={() => { selectedPeers.forEach(peerId => { sendSignal(peerId, 'transfer_request', {files: selectedFiles.map(f => f.file.name)}); }); showToast(`Sending to ${selectedPeers.length} device(s)...`); setSelectedPeers([]); }}>Share with {selectedPeers.length || '...'} device{selectedPeers.length !== 1 ? 's' : ''}</button>
                                        </div>
                                    )}
                                </div>
                            </>
                        )}
                        {activeTab === 'history' && (
                            <div className="w-full max-w-2xl h-full flex flex-col py-4 animate-in slide-in-from-right-8 duration-500">
                                <div className="flex justify-between items-center mb-8"><h2 className="text-2xl font-bold">History</h2><button onClick={() => setActiveTab('radar')} className="glass-button px-6 py-2 rounded-full text-sm font-bold">Done</button></div>
                                <div className="flex-1 overflow-y-auto pr-2 no-scrollbar flex flex-col gap-3">
                                    {history.length === 0 ? (<div className="h-full flex flex-col items-center justify-center opacity-20"><File size={48} className="mb-4" /><p>No activity yet</p></div>) : (
                                        history.map(item => (
                                            <div key={item.id} className="glass-panel p-5 rounded-3xl flex items-center gap-4 group hover:border-white/20 transition-colors">
                                                <div className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center relative">
                                                    {item.type?.startsWith('image/') ? <ImageIcon size={20}/> : item.type?.startsWith('video/') ? <Video size={20}/> : <File size={20}/>}
                                                    <div className={`absolute -top-1 -right-1 w-5 h-5 rounded-full flex items-center justify-center border-2 border-[var(--bg-color)] ${item.status === 'received' ? 'bg-green-500' : 'bg-[var(--accent-primary)]'}`}>
                                                        {item.status === 'received' ? <Download size={10} className="text-white" /> : <UploadCloud size={10} className="text-white" />}
                                                    </div>
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="font-bold truncate text-sm">{item.name}</div>
                                                    <div className="text-[10px] opacity-40 font-medium">{formatSize(item.size)} • {item.sender} • {new Date(item.timestamp).toLocaleTimeString()}</div>
                                                </div>
                                                <div className="flex gap-2">
                                                    {item.fileId && (<a href={`/api/download/${item.fileId}`} download={item.name} className="p-3 bg-white/5 rounded-2xl hover:bg-[var(--accent-primary)]/20 transition-colors text-[var(--accent-primary)]"><Download size={18} /></a>)}
                                                    <button onClick={() => db.history.delete(item.id).then(loadHistory)} className="p-3 bg-white/5 rounded-2xl hover:bg-red-500/20 transition-colors text-red-500"><Trash2 size={18} /></button>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </div>
                        )}
                        {activeTab === 'settings' && (
                            <div className="w-full max-w-md py-4 animate-in slide-in-from-right-8 duration-500">
                                <div className="flex justify-between items-center mb-8"><h2 className="text-2xl font-bold">Settings</h2><button onClick={() => setActiveTab('radar')} className="glass-button px-6 py-2 rounded-full text-sm font-bold">Done</button></div>
                                <div className="space-y-4">
                                    <div className="glass-panel p-6 rounded-[2rem] space-y-4">
                                        <div>
                                            <label className="block text-[10px] font-bold uppercase opacity-30 mb-2 ml-1">Device Name</label>
                                            <input type="text" className="w-full bg-white/5 border border-white/5 rounded-2xl px-4 py-3 outline-none focus:border-[var(--accent-primary)] transition-colors" value={myDevice.name} onChange={e => { setMyDevice({...myDevice, name: e.target.value}); localStorage.setItem('deviceName', e.target.value); }} />
                                        </div>
                                        <div>
                                            <label className="block text-[10px] font-bold uppercase opacity-30 mb-3 ml-1">Security</label>
                                            <div className="flex gap-2">
                                                <button className={`flex-1 py-4 rounded-2xl flex flex-col items-center gap-2 transition-all ${securityMode === 'approval' ? 'bg-[var(--accent-primary)] text-white' : 'bg-white/5'}`} onClick={() => {setSecurityMode('approval'); localStorage.setItem('securityMode', 'approval')}}><Shield size={20} /><span className="text-xs font-bold">Approval</span></button>
                                                <button className={`flex-1 py-4 rounded-2xl flex flex-col items-center gap-2 transition-all ${securityMode === 'pin' ? 'bg-[var(--accent-primary)] text-white' : 'bg-white/5'}`} onClick={() => {setSecurityMode('pin'); localStorage.setItem('securityMode', 'pin')}}><Lock size={20} /><span className="text-xs font-bold">PIN</span></button>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="glass-panel p-6 rounded-[2rem]">
                                        <label className="block text-[10px] font-bold uppercase opacity-30 mb-3 ml-1">Appearance</label>
                                        <div className="flex gap-2">
                                            <button className={`flex-1 py-3 rounded-xl text-xs font-bold transition-all ${theme === 'default' ? 'bg-white/20' : 'bg-white/5'}`} onClick={() => setTheme('default')}>Dark</button>
                                            <button className={`flex-1 py-3 rounded-xl text-xs font-bold transition-all ${theme === 'light' ? 'bg-white/20' : 'bg-white/5'}`} onClick={() => setTheme('light')}>Light</button>
                                        </div>
                                    </div>
                                    <div className="p-6 opacity-30 text-[10px] flex items-center gap-3"><Info size={14} /><span>Files are shared over local network. No internet data is used.</span></div>
                                </div>
                            </div>
                        )}
                    </main>
                    <div className="fixed bottom-12 left-1/2 -translate-x-1/2 z-[200] flex flex-col gap-3 w-full max-w-xs pointer-events-none">
                        {toasts.map(t => (
                            <div key={t.id} className="glass-panel px-6 py-4 rounded-[1.5rem] flex items-center gap-4 animate-in slide-in-from-bottom-8 fade-in duration-500 pointer-events-auto shadow-2xl">
                                <div className={`w-3 h-3 rounded-full ${t.type === 'error' ? 'bg-red-500 shadow-[0_0_12px_rgba(239,68,68,0.5)]' : 'bg-indigo-500 shadow-[0_0_12px_rgba(99,102,241,0.5)]'}`} /><span className="text-sm font-bold tracking-tight">{t.message}</span>
                            </div>
                        ))}
                    </div>
                    {showQR && <QRCodeModal />}
                    {showPinEntry && <PinModal />}
                    {selectedPreview && (
                        <div className="fixed inset-0 bg-black/90 backdrop-blur-xl flex items-center justify-center z-[150]" onClick={() => setSelectedPreview(null)}>
                            <div className="w-full max-w-lg aspect-video glass-panel p-4 rounded-[2.5rem]" onClick={e => e.stopPropagation()}>
                                <div className="flex justify-between items-center mb-4 px-2"><h3 className="font-bold truncate max-w-[200px]">{selectedPreview.name}</h3><button onClick={() => setSelectedPreview(null)} className="p-2 hover:bg-white/10 rounded-full transition-colors"><X size={20}/></button></div>
                                <div className="w-full h-[calc(100%-3rem)] rounded-2xl overflow-hidden bg-black/20"><FilePreview file={selectedPreview} full={true} /></div>
                            </div>
                        </div>
                    )}
                    {selectedPeerDetails && <PeerDetailsModal peer={selectedPeerDetails} custom={peerCustomizations[selectedPeerDetails.uid]} onClose={() => setSelectedPeerDetails(null)} />}
                    {incomingRequests.map(req => (
                        <div key={req.id} className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100] animate-in fade-in duration-300">
                            <div className="glass-panel p-8 rounded-[2rem] max-w-xs w-full text-center animate-in zoom-in-95 duration-300 shadow-2xl">
                                <div className="w-16 h-16 bg-[var(--accent-primary)]/10 rounded-2xl flex items-center justify-center mx-auto mb-6">
                                    <DeviceSilhouette type={req.senderDevice.type} os={req.senderDevice.os} className="w-8 h-8 text-[var(--accent-primary)]" />
                                </div>
                                <h2 className="text-lg font-bold mb-1">{req.senderDevice.name}</h2>
                                <p className="text-xs opacity-40 mb-8 font-medium">Wants to share {req.files.length} item{req.files.length !== 1 ? 's' : ''}</p>
                                <div className="grid grid-cols-2 gap-3">
                                    <button className="py-3 rounded-xl bg-white/5 font-bold text-sm active:scale-95 transition-transform" onClick={() => { sendSignal(req.sender, 'transfer_declined', {}); setIncomingRequests(prev => prev.filter(r => r.id !== req.id)); }}>Decline</button>
                                    <button className="py-3 rounded-xl bg-[var(--accent-primary)] font-bold text-sm text-white active:scale-95 transition-transform" onClick={() => { sendSignal(req.sender, 'transfer_accepted', {}); setIncomingRequests(prev => prev.filter(r => r.id !== req.id)); }}>Accept</button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            );
        }
        const root = ReactDOM.createRoot(document.getElementById('root')); root.render(<App />);
        if ('serviceWorker' in navigator) { navigator.serviceWorker.register('/sw.js'); }
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
        'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js',
        'https://cdn.jsdelivr.net/npm/qrcode@1.5.1/build/qrcode.min.js',
        'https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js',
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

@app.route('/api/events/<uid>')
def events(uid):
    def stream():
        q = []
        with state_lock:
            state["clients"][uid] = q

        while True:
            if q:
                with state_lock:
                    msg = q.pop(0)
                yield f"data: {json.dumps(msg)}\n\n"
            else:
                time.sleep(0.5)
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return Response(stream(), mimetype='text/event-stream')

@app.route('/api/sync', methods=['POST'])
def sync():
    data = request.json
    device = data.get('device')
    uid = device.get('uid')
    now = time.time()

    with state_lock:
        state["devices"][uid] = {**device, "last_seen": now}
        state["devices"] = {k: v for k, v in state["devices"].items() if now - v["last_seen"] < 10}
        for client_id, q in state["clients"].items():
            q.append({"type": "sync", "devices": state["devices"]})

    return jsonify({"status": "ok"})

@app.route('/api/signal', methods=['POST'])
def signal():
    signal_data = request.json
    target = signal_data.get('target')
    with state_lock:
        if target in state["clients"]:
            state["clients"][target].append(signal_data)
    return jsonify({"status": "ok"})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    file_id = request.form.get('file_id')
    chunk_index = int(request.form.get('chunk_index', 0))
    total_chunks = int(request.form.get('total_chunks', 1))
    filename = request.form.get('filename')

    if not file or not file_id or not filename:
        return jsonify({"error": "Missing data"}), 400

    safe_name = secure_filename(filename)
    temp_filename = f"{file_id}_{safe_name}.part"
    filepath = os.path.join(UPLOAD_FOLDER, temp_filename)

    mode = "ab" if chunk_index > 0 else "wb"
    with open(filepath, mode) as f:
        f.write(file.read())

    if chunk_index + 1 == total_chunks:
        final_filename = f"{file_id}_{safe_name}"
        final_path = os.path.join(UPLOAD_FOLDER, final_filename)
        if os.path.exists(final_path):
            os.remove(final_path)
        os.rename(filepath, final_path)
        with state_lock:
            state["files"][file_id] = {
                "filename": safe_name,
                "internal_path": final_filename,
                "timestamp": time.time()
            }
        return jsonify({"status": "complete", "file_id": file_id})

    return jsonify({"status": "chunk_saved", "chunk_index": chunk_index})

@app.route('/api/cancel_upload', methods=['POST'])
def cancel_upload():
    data = request.json
    file_id = data.get('file_id')
    filename = data.get('filename')
    if not file_id or not filename:
        return jsonify({"error": "Missing data"}), 400
    safe_name = secure_filename(filename)
    temp_filename = f"{file_id}_{safe_name}.part"
    filepath = os.path.join(UPLOAD_FOLDER, temp_filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    return jsonify({"status": "cancelled"})

@app.route('/api/download/<file_id>')
def download_file(file_id):
    with state_lock:
        file_meta = state["files"].get(file_id)
    if not file_meta:
        return "File not found", 404
    return send_from_directory(UPLOAD_FOLDER, file_meta["internal_path"], as_attachment=True, download_name=file_meta["filename"])

if __name__ == '__main__':
    threading.Thread(target=cleanup_uploads, daemon=True).start()
    print(f"AirShare Py running at http://{LOCAL_IP}:{PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=True, threaded=True)
