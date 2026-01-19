import { NavLink } from 'react-router-dom'
import { Home, Calendar, List, CreditCard } from 'lucide-react'
import ThemeToggle from './ThemeToggle'
import './Navbar.css'

function Navbar() {
  return (
    <nav className="navbar">
      <div className="nav-brand">
        <span className="logo-text">Gold</span>
        <span className="logo-text-accent">Road</span>
      </div>
      <div className="nav-content">
        <ul className="nav-links">
          <li>
            <NavLink to="/" className={({ isActive }) => isActive ? 'active' : ''}>
              <Home size={18} />
              <span>Home</span>
            </NavLink>
          </li>
          <li>
            <NavLink to="/orders-by-day" className={({ isActive }) => isActive ? 'active' : ''}>
              <Calendar size={18} />
              <span>Orders by Day</span>
            </NavLink>
          </li>
          <li>
            <NavLink to="/all-orders" className={({ isActive }) => isActive ? 'active' : ''}>
              <List size={18} />
              <span>All Orders</span>
            </NavLink>
          </li>
          <li>
            <NavLink to="/payment-processing" className={({ isActive }) => isActive ? 'active' : ''}>
              <CreditCard size={18} />
              <span>Payment Processing</span>
            </NavLink>
          </li>
        </ul>
        <ThemeToggle />
      </div>
    </nav>
  )
}

export default Navbar
