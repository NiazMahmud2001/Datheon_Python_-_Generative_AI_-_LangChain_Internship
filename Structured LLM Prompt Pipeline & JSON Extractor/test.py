import os 
import fitz

print(os.listdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'some_demo_invoices')))


inv_data = fitz.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), f'some_demo_invoices/Black and White Minimalist Professional Invoice.pdf'))
print(inv_data)