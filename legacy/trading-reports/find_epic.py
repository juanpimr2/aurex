"""
Utilidad para buscar EPICs de activos en Capital.com
====================================================
Usa esto para encontrar los nombres correctos de acciones.
"""
import requests
from config import API_KEY, PASSWORD, EMAIL, BASE_URL


def search_markets(search_term: str):
    """Buscar activos por nombre"""
    
    session = requests.Session()
    
    # Login
    headers = {"X-CAP-API-KEY": API_KEY, "Content-Type": "application/json"}
    data = {"identifier": EMAIL, "password": PASSWORD}
    
    r = session.post(f"{BASE_URL}/session", headers=headers, json=data)
    
    if r.status_code != 200:
        print(f"❌ Error de autenticación: {r.status_code}")
        return
    
    cst = r.headers.get('CST')
    token = r.headers.get('X-SECURITY-TOKEN')
    
    session.headers.update({
        'X-SECURITY-TOKEN': token,
        'CST': cst,
        'Content-Type': 'application/json'
    })
    
    print(f"✅ Conectado\n")
    print(f"🔍 Buscando: {search_term}\n")
    
    # Buscar
    r = session.get(f"{BASE_URL}/markets", params={'searchTerm': search_term})
    
    if r.status_code != 200:
        print(f"❌ Error en búsqueda: {r.status_code}")
        return
    
    data = r.json()
    markets = data.get('markets', [])
    
    if not markets:
        print("⚠️ No se encontraron resultados")
        return
    
    print(f"📊 Encontrados {len(markets)} resultados:\n")
    print("-" * 80)
    
    for market in markets[:20]:  # Mostrar primeros 20
        epic = market.get('epic', 'N/A')
        name = market.get('instrumentName', 'N/A')
        type_ = market.get('instrumentType', 'N/A')
        status = market.get('marketStatus', 'N/A')
        
        print(f"EPIC: {epic}")
        print(f"  Nombre: {name}")
        print(f"  Tipo: {type_}")
        print(f"  Estado: {status}")
        print("-" * 80)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        search_term = ' '.join(sys.argv[1:])
    else:
        search_term = input("🔍 Buscar activo: ")
    
    search_markets(search_term)
