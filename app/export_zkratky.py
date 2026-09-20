import sys
import json
import os

def main():
    print("Exportuji zkratky ze soucasne databaze...")
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from services.dbf_service import DbfService
    
    # Cesta k datům
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DATA")
    try:
        db = DbfService(data_path)
        
        # Získání zkratek
        s2 = {r.get('KOD'): str(r.get('SYMBOL', '')).strip() for r in db.read_all('tsd02') if str(r.get('SYMBOL', '')).strip()}
        s3 = {r.get('KOD'): str(r.get('SYMBOL', '')).strip() for r in db.read_all('tsd03') if str(r.get('SYMBOL', '')).strip()}
        
        # Zápis do default_symbols.py
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_symbols.py")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('DEFAULT_SESTAVY_SYMBOLY = ' + json.dumps(s2, indent=4) + '\n')
            f.write('DEFAULT_DILY_SYMBOLY = ' + json.dumps(s3, indent=4) + '\n')
            
        print(f"Uspech! Celkem exportovano {len(s2)} zkratek sestav a {len(s3)} zkratek dilu.")
        print("Tento seznam je nyni zabalen pro prenos a automaticky se vyplni prazdnym polozkam pri dalsim spusteni.")
    except Exception as e:
        print("Chyba pri exportu:", str(e))

if __name__ == "__main__":
    main()
