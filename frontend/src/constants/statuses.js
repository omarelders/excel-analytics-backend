/**
 * Centralized constants for shipment statuses.
 * This provides a local fallback, but should be synced with the backend /statuses endpoint.
 */

// ALL statuses can now be changed (no restrictions on source status)
// Synced with backend constants.py
export const CHANGEABLE_STATUSES = [
  'طلب الشحن',
  'طلب شحن',
  'تم الاستلام بالمخزن',
  'قيد التوصيل',
  'تم التسليم',
  'مرتجع',
  'تسليم جزئي',
  'ملغى'
]

// Statuses that orders can be changed TO (target statuses)
export const TARGET_STATUSES = [
  'تم التسليم',
  'مرتجع',
  'تسليم جزئي',
  'قيد التوصيل'
]

// All possible statuses (unique values only)
export const ALL_STATUSES = [
  ...new Set([...CHANGEABLE_STATUSES, ...TARGET_STATUSES])
]

// Status display colors
export const STATUS_COLORS = {
  'تم التسليم': 'success',
  'تم الاستلام بالمخزن': 'info',
  'طلب الشحن': 'pending',
  'طلب شحن': 'pending',
  'مرتجع': 'error',
  'ملغى': 'error',
  'قيد التوصيل': 'info',
  'تسليم جزئي': 'warning'
}

/**
 * Get the color class for a given status
 * @param {string} status - The status string
 * @returns {string} - Color class name
 */
export const getStatusColor = (status) => {
  if (!status) return 'default'
  
  // Check direct match first
  if (STATUS_COLORS[status]) {
    return STATUS_COLORS[status]
  }
  
  // Fallback pattern matching (for partial matches)
  if (status.includes('تم')) return 'success'
  if (status.includes('الاستلام')) return 'info'
  if (status.includes('ملغى')) return 'error'
  
  return 'default'
}

/**
 * Check if a status can be changed
 * @param {string} status - The current status
 * @returns {boolean}
 */
export const canChangeStatus = (status) => {
  return CHANGEABLE_STATUSES.includes(status)
}
