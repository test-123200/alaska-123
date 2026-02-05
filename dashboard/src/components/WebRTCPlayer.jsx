import { useRef, useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';

// Helper to wait for ICE candidates
const waitForCandidates = (pc) => {
    return new Promise((resolve) => {
        if (pc.iceGatheringState === 'complete') {
            resolve();
        } else {
            const checkState = () => {
                if (pc.iceGatheringState === 'complete') {
                    pc.removeEventListener('icegatheringstatechange', checkState);
                    resolve();
                }
            };
            pc.addEventListener('icegatheringstatechange', checkState);
        }
    });
};


export default function WebRTCPlayer({ employeeId, onClose }) {
    const videoRef = useRef(null);
    const [pc, setPc] = useState(null);
    const [status, setStatus] = useState('Initializing...');

    useEffect(() => {
        const newPc = new RTCPeerConnection({
            iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
        });

        newPc.ontrack = (event) => {
            console.log("Track received:", event.streams[0]);
            if (videoRef.current) {
                videoRef.current.srcObject = event.streams[0];
            }
        };

        newPc.oniceconnectionstatechange = () => {
            setStatus(`Connection State: ${newPc.iceConnectionState}`);
            if (newPc.iceConnectionState === 'disconnected') {
                onClose();
            }
        };

        setPc(newPc);

        // Subscribe to signaling channel
        const channel = supabase.channel(`signaling-${employeeId}`)
            .on('postgres_changes',
                { event: 'INSERT', schema: 'public', table: 'signaling', filter: `sender_id=eq.${employeeId}` },
                (payload) => {
                    handleSignal(newPc, payload.new);
                }
            )
            .subscribe();

        // Send START_VIDEO command
        startVideo(employeeId);

        return () => {
            console.log("Cleaning up WebRTC");
            newPc.close();
            supabase.removeChannel(channel);
        };
    }, [employeeId]);

    const startVideo = async (empId) => {
        // Send signal to agent to start streaming
        await supabase.from('signaling').insert({
            recipient_id: empId,
            type: 'START_VIDEO',
            payload: {}
        });
        setStatus('Requested Video...');
    };

    const handleSignal = async (peerConnection, signal) => {
        console.log("Received signal:", signal.type);

        if (signal.type === 'OFFER') {
            setStatus('Received Offer. Negotiating...');
            try {
                const desc = new RTCSessionDescription(signal.payload);
                await peerConnection.setRemoteDescription(desc);

                const answer = await peerConnection.createAnswer();
                await peerConnection.setLocalDescription(answer);

                // Send Answer
                await supabase.from('signaling').insert({
                    recipient_id: employeeId,
                    type: 'ANSWER',
                    payload: { sdp: peerConnection.localDescription.sdp, type: peerConnection.localDescription.type }
                });
                setStatus('Streaming...');
            } catch (err) {
                console.error("Error handling offer:", err);
                setStatus('Error negotiating');
            }
        }
    };

    return (
        <div className="fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center z-50">
            <div className="bg-white p-4 rounded-lg shadow-xl max-w-4xl w-full">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-bold">Remote Stream</h3>
                    <button onClick={onClose} className="text-red-500 font-bold px-2">Close</button>
                </div>
                <div className="relative aspect-video bg-gray-900 rounded overflow-hidden">
                    <video ref={videoRef} autoPlay playsInline controls className="w-full h-full object-contain" />
                    <div className="absolute top-2 left-2 bg-black bg-opacity-50 text-white text-xs px-2 py-1 rounded">
                        {status}
                    </div>
                </div>
            </div>
        </div>
    );
}
