import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import EmployeeDetail from './pages/EmployeeDetail';

function App() {
    return (
        <Router>
            <div className="min-h-screen bg-gray-50 text-gray-900">
                <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/employee/:id" element={<EmployeeDetail />} />
                </Routes>
            </div>
        </Router>
    );
}

export default App;
