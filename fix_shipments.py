"""Temporary script to fix shipments.py auth"""
import pathlib

p = pathlib.Path("routers/shipments.py")
c = p.read_text(encoding="utf-8")

# Fix 1: Add auth dependency to imports and router
c = c.replace(
    "from fastapi import APIRouter, UploadFile, File, HTTPException\r\nfrom constants import CHANGEABLE_STATUSES, TARGET_STATUSES\r\n\r\nrouter = APIRouter()",
    "from fastapi import APIRouter, UploadFile, File, HTTPException, Depends\r\nfrom constants import CHANGEABLE_STATUSES, TARGET_STATUSES\r\nfrom dependencies import get_current_user\r\n\r\nrouter = APIRouter(dependencies=[Depends(get_current_user)])"
)

# Fix 2: Sanitize error messages
c = c.replace(
    'raise HTTPException(status_code=500, detail=f"Failed to delete shipment: {str(e)}")',
    'print(f"Error deleting shipment: {e}")\r\n        raise HTTPException(status_code=500, detail="Failed to delete shipment")'
)
c = c.replace(
    'raise HTTPException(status_code=500, detail=f"Failed to restore shipment: {str(e)}")',
    'print(f"Error restoring shipment: {e}")\r\n        raise HTTPException(status_code=500, detail="Failed to restore shipment")'
)
c = c.replace(
    'raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")',
    'print(f"Error updating status: {e}")\r\n        raise HTTPException(status_code=500, detail="Failed to update status")'
)
c = c.replace(
    'raise HTTPException(status_code=500, detail=f"Failed to update shipment: {str(e)}")',
    'print(f"Error updating shipment: {e}")\r\n        raise HTTPException(status_code=500, detail="Failed to update shipment")'
)
c = c.replace(
    'raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")',
    'print(f"Error deleting file: {e}")\r\n        raise HTTPException(status_code=500, detail="Failed to delete file")'
)

p.write_text(c, encoding="utf-8")
print("shipments.py patched successfully!")
