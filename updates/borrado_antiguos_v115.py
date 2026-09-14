"""Borrado simple desde el catálogo real de Wallapop. No depende de publicados.json."""
import json, os, queue, re, threading, time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote

class Cancelado(Exception): pass

def escribir_json(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp'); tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8'); os.replace(tmp,path)

def identidad(url):
    try:
        u=urlparse(str(url)); host=(u.hostname or '').lower()
        if u.scheme!='https' or not (host=='wallapop.com' or host.endswith('.wallapop.com')): return None
        m=re.fullmatch(r'/item/(?:[^/]*-)?([0-9]+)/*',unquote(u.path))
        return m.group(1) if m else None
    except Exception: return None

def boton_unico(scope, patron):
    hits=[]
    for role in ('button','menuitem'):
        loc=scope.get_by_role(role,name=re.compile(patron,re.I))
        for i in range(loc.count()):
            e=loc.nth(i)
            if e.is_visible() and e.is_enabled(): hits.append(e)
    return hits[0] if len(hits)==1 else None

def abrir_mis_productos(page):
    """Abre directamente el catálogo publicado usando la misma sesión que Publicar."""
    destino = 'https://es.wallapop.com/app/catalog/published'
    page.goto(destino, wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(2200)

    url = (page.url or '').lower()
    cuerpo = ''
    try:
        cuerpo = page.locator('body').inner_text(timeout=3000).lower()
    except Exception:
        pass
    if ('login' in url or 'iniciar sesión' in cuerpo or 'inicia sesión' in cuerpo):
        raise RuntimeError('Wallapop pide iniciar sesión. Inicia sesión en el Chromium de DIAGPROG5 y vuelve a intentarlo.')

    if '/app/catalog' not in (page.url or ''):
        raise RuntimeError('Wallapop no abrió Mis productos. URL actual: ' + str(page.url))

def descubrir(page, cantidad, stop):
    abrir_mis_productos(page)
    estable=0; anterior=0
    for _ in range(80):
        if stop.is_set(): raise Cancelado()
        page.evaluate('window.scrollTo(0, document.body.scrollHeight)'); page.wait_for_timeout(650)
        n=page.locator('a[href*="/item/"], a[href*="/app/catalog/"]').count()
        if n<=anterior: estable+=1
        else: estable=0; anterior=n
        if estable>=4: break
    raw=page.locator('a[href*="/item/"]').evaluate_all("els => els.map(e => ({href:e.href,title:(e.getAttribute('aria-label')||e.innerText||'').trim()}))")
    seen=set(); items=[]
    for x in raw:
        uid=identidad(x.get('href',''))
        if uid and uid not in seen:
            seen.add(uid); items.append({'uid':uid,'url':x['href'].split('?')[0],'titulo':(x.get('title') or 'Anuncio Wallapop').split('\n')[0][:120]})
    if not items: raise RuntimeError('Abrí Mis productos, pero no encontré enlaces de anuncios. URL actual: ' + str(page.url))
    return list(reversed(items))[:cantidad], len(items)

def respuesta_borrado(response, uid):
    """Reconoce varias formas usadas por Wallapop al retirar un anuncio."""
    try:
        u=urlparse(response.url); host=(u.hostname or '').lower()
        if not (host=='wallapop.com' or host.endswith('.wallapop.com')):
            return False
        metodo=response.request.method.upper()
        ruta=unquote(u.path).lower()
        if not (200 <= response.status < 300) or metodo not in ('DELETE','PATCH','POST','PUT'):
            return False
        palabras=('delete','remove','unpublish','deactivate','sold','catalog','item','product')
        return uid in ruta and any(x in ruta for x in palabras)
    except Exception:
        return False

def _visible_enabled(locator):
    try:
        return locator.is_visible() and locator.is_enabled()
    except Exception:
        return False

def _buscar_control(scope, patrones, roles=('button','menuitem','link')):
    """Devuelve el primer control visible cuyo nombre encaje con alguno de los patrones."""
    for patron in patrones:
        rx=re.compile(patron,re.I)
        for role in roles:
            try:
                loc=scope.get_by_role(role,name=rx)
                for i in range(min(loc.count(),30)):
                    el=loc.nth(i)
                    if _visible_enabled(el):
                        return el
            except Exception:
                pass
    return None

def _click_texto(scope, patrones):
    for patron in patrones:
        try:
            loc=scope.get_by_text(re.compile(patron,re.I),exact=False)
            for i in range(min(loc.count(),40)):
                el=loc.nth(i)
                if _visible_enabled(el):
                    el.click(timeout=4500)
                    return True
        except Exception:
            pass
    return False

def _click_css_eliminar(page):
    """Respaldo para iconos/menús sin texto accesible."""
    selectores=[
        '[data-testid*="delete" i]', '[data-testid*="remove" i]',
        '[aria-label*="eliminar" i]', '[aria-label*="borrar" i]', '[aria-label*="delete" i]',
        '[title*="eliminar" i]', '[title*="borrar" i]', '[title*="delete" i]'
    ]
    for sel in selectores:
        try:
            loc=page.locator(sel)
            for i in range(min(loc.count(),20)):
                el=loc.nth(i)
                if _visible_enabled(el):
                    el.click(timeout=4500)
                    return True
        except Exception:
            pass
    return False

def _resolver_dialogo_borrado(page):
    """Resuelve los diálogos actuales de Wallapop, incluido el motivo del borrado."""
    page.wait_for_timeout(450)
    scopes=[page]
    try:
        dialogs=page.get_by_role('dialog')
        visibles=[dialogs.nth(i) for i in range(min(dialogs.count(),12)) if dialogs.nth(i).is_visible()]
        if visibles:
            scopes=visibles
    except Exception:
        pass

    for scope in scopes:
        motivo=_buscar_control(scope,[
            r'^(otro|otros motivos?|otro motivo)$',
            r'ya no (quiero|deseo) vender(lo)?',
            r'he cambiado de opini[oó]n',
            r'no quiero vender(lo)?',
        ],roles=('radio','button'))
        if motivo is not None:
            try:
                motivo.click(timeout=4000); page.wait_for_timeout(300)
            except Exception:
                pass
        else:
            _click_texto(scope,[r'^otro(s)? motivo(s)?$',r'ya no .*vender',r'he cambiado de opini[oó]n'])
            page.wait_for_timeout(250)

        confirm=_buscar_control(scope,[
            r'^s[ií][, ]+(eliminar|borrar|retirar)( (este )?(anuncio|producto|art[ií]culo|item))?$',
            r'^(eliminar|borrar|retirar)( (este )?(anuncio|producto|art[ií]culo|item))?$',
            r'^confirmar$', r'^aceptar$'
        ],roles=('button','menuitem'))
        if confirm is not None:
            confirm.click(timeout=5000)
            return True
    return False

def _abrir_menu_y_eliminar(page):
    patrones_eliminar=[
        r'^eliminar( (este )?(anuncio|producto|art[ií]culo|item))?$',
        r'^borrar( (este )?(anuncio|producto|art[ií]culo|item))?$',
        r'^retirar( (este )?(anuncio|producto|art[ií]culo|item))?$',
        r'^delete( (this )?(listing|product|item))?$'
    ]
    boton=_buscar_control(page,patrones_eliminar)
    if boton is not None:
        boton.click(timeout=5000); return True

    menu=_buscar_control(page,[
        r'^(m[aá]s opciones|opciones|acciones|m[aá]s|more|more options|manage|gestionar)$',
        r'^(men[uú]|menu)$'
    ],roles=('button','menuitem'))
    if menu is None:
        for sel in ('button[aria-haspopup="menu"]','[data-testid*="menu" i]','button[aria-label*="option" i]'):
            try:
                loc=page.locator(sel)
                visibles=[loc.nth(i) for i in range(min(loc.count(),20)) if _visible_enabled(loc.nth(i))]
                if visibles:
                    menu=visibles[-1]
                    break
            except Exception:
                pass
    if menu is not None:
        menu.click(timeout=5000); page.wait_for_timeout(500)
        boton=_buscar_control(page,patrones_eliminar)
        if boton is not None:
            boton.click(timeout=5000); return True
        if _click_texto(page,[r'^eliminar',r'^borrar',r'^retirar']):
            return True

    if _click_css_eliminar(page):
        return True

    editar=_buscar_control(page,[
        r'^(editar|gestionar)( (el )?(anuncio|producto|art[ií]culo))?$',
        r'^edit( listing| product)?$'
    ])
    if editar is not None:
        editar.click(timeout=5000); page.wait_for_timeout(1000)
        boton=_buscar_control(page,patrones_eliminar)
        if boton is not None:
            boton.click(timeout=5000); return True
        if _click_texto(page,[r'^eliminar',r'^borrar',r'^retirar']):
            return True
        if _click_css_eliminar(page):
            return True
    return False

def _item_sigue_en_catalogo(page, uid, stop):
    """Verificación fuerte: vuelve a Mis productos y busca el UID en todo el catálogo."""
    abrir_mis_productos(page)
    estable=0; anterior=-1
    for _ in range(80):
        if stop.is_set(): raise Cancelado()
        hrefs=page.locator('a[href*="/item/"]').evaluate_all('els => els.map(e => e.href)')
        ids={identidad(h) for h in hrefs}; ids.discard(None)
        n=len(ids)
        if n==anterior: estable+=1
        else: estable=0; anterior=n
        if estable>=3:
            return uid in ids
        page.evaluate('window.scrollTo(0, document.body.scrollHeight)'); page.wait_for_timeout(500)
    hrefs=page.locator('a[href*="/item/"]').evaluate_all('els => els.map(e => e.href)')
    return uid in {identidad(h) for h in hrefs}

def eliminar(page, entry, stop):
    if stop.is_set(): raise Cancelado()
    page.goto(entry['url'],wait_until='domcontentloaded',timeout=35000); page.wait_for_timeout(1600)
    if identidad(page.url)!=entry['uid']:
        raise RuntimeError('Wallapop no abrió el anuncio previsto; no se borró nada.')

    confirmed=[]
    def onresp(r):
        if respuesta_borrado(r,entry['uid']): confirmed.append(True)
    page.on('response',onresp)
    try:
        if not _abrir_menu_y_eliminar(page):
            raise RuntimeError('No encontré la acción Eliminar/Borrar/Retirar en este anuncio.')

        for _ in range(3):
            if confirmed: break
            if not _resolver_dialogo_borrado(page): break
            page.wait_for_timeout(650)

        for _ in range(24):
            if confirmed: return
            if stop.is_set(): raise Cancelado()
            try:
                body=page.locator('body').inner_text(timeout=700)
                if re.search(r'(anuncio|producto|art[ií]culo).{0,50}(eliminado|borrado|retirado|despublicado|ya no est[aá] disponible)',body,re.I|re.S):
                    return
            except Exception:
                pass
            if identidad(page.url)!=entry['uid']:
                return
            page.wait_for_timeout(250)

        if not _item_sigue_en_catalogo(page,entry['uid'],stop):
            return
        raise RuntimeError('Wallapop mantuvo el anuncio en Mis productos después de confirmar. Se detuvo para evitar borrar otro anuncio.')
    finally:
        page.remove_listener('response',onresp)

class Panel:
    def __init__(self,g):
        import customtkinter as ctk
        from tkinter import messagebox
        self.g,self.ctk,self.msg=g,ctk,messagebox; self.root=g['ventana']; self.busy=False; self.stop=threading.Event(); self.events=queue.Queue()
        self.data=Path(g['CARPETA_DATOS_USUARIO'])/'borrado_antiguos'; self.data.mkdir(parents=True,exist_ok=True)
        cfg={'cantidad':1,'pausa':3}
        try:
            old=json.loads((self.data/'ajustes_simple.json').read_text(encoding='utf-8')); cfg.update(old)
        except Exception: pass
        tab=g.get('tab_borrar') or g['tabs'].add('Borrar antiguos')
        for child in tab.winfo_children(): child.destroy()
        scroll=ctk.CTkScrollableFrame(tab); scroll.pack(fill='both',expand=True,padx=18,pady=18)
        ctk.CTkLabel(scroll,text='Borrar anuncios antiguos',font=('Segoe UI',26,'bold')).pack(anchor='w',padx=18,pady=(18,5))
        ctk.CTkLabel(scroll,text='DIAGPROG5 mira directamente los anuncios de tu cuenta de Wallapop. No usa el historial ni los enlaces guardados por el bot.',wraplength=850,justify='left').pack(anchor='w',padx=18,pady=(0,18))
        form=ctk.CTkFrame(scroll); form.pack(fill='x',padx=18,pady=8)
        ctk.CTkLabel(form,text='Cantidad a borrar').grid(row=0,column=0,padx=18,pady=14,sticky='w'); self.cantidad=ctk.CTkEntry(form,width=100); self.cantidad.insert(0,str(cfg['cantidad'])); self.cantidad.grid(row=0,column=1,padx=12)
        ctk.CTkLabel(form,text='Pausa entre borrados (segundos)').grid(row=1,column=0,padx=18,pady=14,sticky='w'); self.pausa=ctk.CTkEntry(form,width=100); self.pausa.insert(0,str(cfg['pausa'])); self.pausa.grid(row=1,column=1,padx=12)
        self.start_button=ctk.CTkButton(scroll,text='🗑  BORRAR LOS MÁS ANTIGUOS',height=52,font=('Segoe UI',16,'bold'),fg_color='#a63838',hover_color='#7d2929',command=self.start); self.start_button.pack(fill='x',padx=18,pady=(18,8))
        self.stop_button=ctk.CTkButton(scroll,text='Detener',state='disabled',command=self.cancel); self.stop_button.pack(anchor='w',padx=18,pady=5)
        self.status=ctk.CTkLabel(scroll,text='Listo. Para la primera prueba usa cantidad = 1.',wraplength=850,justify='left'); self.status.pack(anchor='w',padx=18,pady=12)
        self.progress=ctk.CTkProgressBar(scroll); self.progress.set(0); self.progress.pack(fill='x',padx=18,pady=6)
        self.log=ctk.CTkTextbox(scroll,height=210); self.log.pack(fill='x',padx=18,pady=10); self.log.configure(state='disabled')
        self.root.after(150,self.poll)
    def config(self):
        n=int(self.cantidad.get()); p=float(self.pausa.get())
        if not 1<=n<=50: raise ValueError('La cantidad debe estar entre 1 y 50.')
        if not 1<=p<=120: raise ValueError('La pausa debe estar entre 1 y 120 segundos.')
        return n,p
    def start(self):
        if self.busy:return
        try:
            n,p=self.config()
            if self.g.get('cola_en_ejecucion') or self.g['_publicador'].ocupado(): raise ValueError('Detén primero la cola/publicación actual.')
            if not self.msg.askyesno('Confirmar',f'DIAGPROG5 abrirá tu perfil de Wallapop y eliminará hasta {n} de los anuncios más antiguos que encuentre.\n\nEsta acción no se puede deshacer. ¿Continuar?'): return
            escribir_json(self.data/'ajustes_simple.json',{'cantidad':n,'pausa':p}); self.busy=True; self.stop.clear(); self.start_button.configure(state='disabled'); self.stop_button.configure(state='normal'); self.progress.set(0)
            threading.Thread(target=self.worker,args=(n,p),daemon=True).start()
        except Exception as e:self.msg.showerror('Borrar antiguos',str(e))
    def cancel(self): self.stop.set(); self.status.configure(text='Deteniendo…')
    def worker(self,n,pausa):
        ok=errors=0; page=operation=None; session=self.data/('directo_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
        try:
            from dp5_runtime import bloquear_operacion
            operation=bloquear_operacion(self.g['CARPETA_DATOS_USUARIO']); session.mkdir(parents=True,exist_ok=True)
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                self.events.put(('status','Abriendo Chromium y entrando en Wallapop…')); self.g['_asegurar_chromium_controlable'](); port=int(self.g['obtener_puerto_chromium']())
                browser=self.g['_conectar_playwright_cdp'](p) if callable(self.g.get('_conectar_playwright_cdp')) else p.chromium.connect_over_cdp(f'http://127.0.0.1:{port}',timeout=20000)
                if not browser.contexts: raise RuntimeError('Chromium no tiene una sesión disponible.')
                page=browser.contexts[0].new_page(); self.events.put(('status','Buscando tus anuncios directamente en Wallapop…'))
                plan,total=descubrir(page,n,self.stop); escribir_json(session/'plan.json',plan); self.events.put(('log',f'Wallapop: {total} anuncios encontrados. Se procesarán {len(plan)}.'))
                for i,e in enumerate(plan,1):
                    if self.stop.is_set():break
                    try:
                        self.events.put(('status',f'Borrando {i}/{len(plan)}: {e["titulo"]}')); self.events.put(('log','Abriendo: '+e['url'])); eliminar(page,e,self.stop); ok+=1; self.events.put(('log','✓ Eliminado: '+e['titulo']))
                    except Cancelado: break
                    except Exception as ex:
                        errors+=1; self.events.put(('log','✗ Detenido: '+str(ex)))
                        try: page.screenshot(path=str(session/'error.png'),full_page=True); (session/'error.html').write_text(page.content(),encoding='utf-8')
                        except Exception: pass
                        break
                    self.events.put(('progress',(i/len(plan),f'{i}/{len(plan)} · {ok} eliminados')))
                    if i<len(plan) and self.stop.wait(pausa):break
                page.close()
        except Exception as e: errors+=1; self.events.put(('log','Error: '+str(e)))
        finally:
            if operation is not None: operation.close()
            self.events.put(('done',f'Finalizado: {ok} eliminado(s), {errors} incidencia(s).'))
    def poll(self):
        try:
            while True:
                kind,val=self.events.get_nowait()
                if kind=='status':self.status.configure(text=val)
                elif kind=='log':self.log.configure(state='normal');self.log.insert('end',val+'\n');self.log.see('end');self.log.configure(state='disabled')
                elif kind=='progress':self.progress.set(val[0]);self.status.configure(text=val[1])
                elif kind=='done':self.busy=False;self.start_button.configure(state='normal');self.stop_button.configure(state='disabled');self.status.configure(text=val)
        except queue.Empty:pass
        self.root.after(150,self.poll)

def instalar_panel(g):
    old=g['cargar_config_rotacion']
    def manual():
        cfg=old();cfg['activo']=False;return cfg
    g['cargar_config_rotacion']=manual;g['_v102_rotacion_activa']=lambda:False;g['gestionar_rotacion_limite_wallapop']=lambda *a,**kw:(False,'Borrado manual independiente.');g['var_rotacion_activa'].set(False)
    g['_panel_borrado_v104']=Panel(g)
