import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';
import { Link } from 'react-router-dom';
import { Monitor, Clock } from 'lucide-react';

export default function Dashboard() {
    const [employees, setEmployees] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchEmployees();

        // Subscribe to new employees
        const channel = supabase.channel('employees_list')
            .on('postgres_changes', { event: '*', schema: 'public', table: 'employees' }, payload => {
                fetchEmployees();
            })
            .subscribe();

        return () => {
            supabase.removeChannel(channel);
        };
    }, []);

    const fetchEmployees = async () => {
        const { data } = await supabase.from('employees').select('*').order('last_seen', { ascending: false });
        if (data) setEmployees(data);
        setLoading(false);
    };

    return (
        <div className="p-8 max-w-7xl mx-auto">
            <h1 className="text-3xl font-bold mb-8 text-gray-800">Monitoring Dashboard</h1>

            {loading ? (
                <div>Loading...</div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {employees.map((emp) => (
                        <Link key={emp.id} to={`/employee/${emp.id}`} className="block">
                            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow">
                                <div className="flex items-center justify-between mb-4">
                                    <div className="flex items-center space-x-3">
                                        <div className="p-2 bg-blue-50 rounded-lg">
                                            <Monitor className="text-blue-600 w-6 h-6" />
                                        </div>
                                        <div>
                                            <h3 className="font-semibold text-gray-900">{emp.hostname}</h3>
                                            <p className="text-sm text-gray-500">{emp.ip_address || 'Unknown IP'}</p>
                                        </div>
                                    </div>
                                    <div className={`w-3 h-3 rounded-full ${isOnline(emp.last_seen) ? 'bg-green-500' : 'bg-gray-300'}`} />
                                </div>
                                <div className="flex items-center text-sm text-gray-500 mt-4">
                                    <Clock className="w-4 h-4 mr-2" />
                                    Last seen: {new Date(emp.last_seen).toLocaleString()}
                                </div>
                            </div>
                        </Link>
                    ))}
                    {employees.length === 0 && (
                        <div className="col-span-3 text-center text-gray-400 py-12">No agents connected yet.</div>
                    )}
                </div>
            )}
        </div>
    );
}

function isOnline(dateString) {
    const diff = new Date() - new Date(dateString);
    return diff < 60000; // < 1 minute considers online
}
