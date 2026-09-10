import os
import io
import math
import base64
import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from supabase import create_client, Client
import resend

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'cotas-engemat-2026-xK9mP3rQv')
app.permanent_session_lifetime = datetime.timedelta(hours=8)

# ─── Configurações de Ambiente ────────────────────────────────────────────────
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'onboarding@resend.dev')
APP_PASSWORD = os.environ.get('APP_PASSWORD', 'cotas25@!')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
resend.api_key = RESEND_API_KEY


# ─── Helpers ──────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def _num(v):
    try:
        f = float(v) if v is not None else 0.0
        return 0.0 if math.isnan(f) else f
    except (ValueError, TypeError):
        return 0.0


def fetch_obras():
    response = supabase.table('obras').select('*').order('obra').execute()
    return response.data


def clean_obra(o):
    return {
        "tipo": str(o.get('tipo', '') or '').strip(),
        "obra": str(o.get('obra', '') or '').strip(),
        "qtd_func": int(_num(o.get('qtd_func', 0))),
        "nec_apr": int(_num(o.get('nec_apr', 0))),
        "atual_apr": int(_num(o.get('atual_apr', 0))),
        "def_apr": int(_num(o.get('def_apr', 0))),
        "status_apr": str(o.get('status_apr', '') or '').strip(),
        "nec_pcd": int(_num(o.get('nec_pcd', 0))),
        "atual_pcd": int(_num(o.get('atual_pcd', 0))),
        "def_pcd": int(_num(o.get('def_pcd', 0))),
        "status_pcd": str(o.get('status_pcd', '') or '').strip(),
        "atualizado_em": datetime.datetime.now().isoformat()
    }


def calcular_stats(obras):
    total_obras = len(obras)
    total_func = int(sum(_num(o.get('qtd_func')) for o in obras))
    apr_at = int(sum(_num(o.get('atual_apr')) for o in obras))
    pcd_at = int(sum(_num(o.get('atual_pcd')) for o in obras))
    
    pend_apr = sum(1 for o in obras if 'abaixo' in str(o.get('status_apr','')).lower())
    pend_pcd = sum(1 for o in obras if 'abaixo' in str(o.get('status_pcd','')).lower())
    
    falta_apr = int(sum(abs(_num(o.get('def_apr'))) for o in obras if _num(o.get('def_apr')) < 0))
    falta_pcd = int(sum(abs(_num(o.get('def_pcd'))) for o in obras if _num(o.get('def_pcd')) < 0))

    por_status_apr = {"abaixo": pend_apr, "dentro": 0, "acima": 0}
    por_status_pcd = {"abaixo": pend_pcd, "dentro": 0, "acima": 0}
    por_tipo = {}

    for o in obras:
        # Status APR
        st_a = str(o.get('status_apr','')).lower()
        if 'dentro' in st_a: por_status_apr["dentro"] += 1
        elif 'acima' in st_a: por_status_apr["acima"] += 1
        # Status PCD
        st_p = str(o.get('status_pcd','')).lower()
        if 'dentro' in st_p: por_status_pcd["dentro"] += 1
        elif 'acima' in st_p: por_status_pcd["acima"] += 1
        # Tipo
        t = str(o.get('tipo', '')).upper()
        if not t: t = "OUTROS"
        por_tipo[t] = por_tipo.get(t, 0) + 1

    return {
        "total_obras": total_obras,
        "total_func": total_func,
        "apr_at": apr_at,
        "pcd_at": pcd_at,
        "pend_apr": pend_apr,
        "pend_pcd": pend_pcd,
        "falta_apr": falta_apr,
        "falta_pcd": falta_pcd,
        "por_status_apr": por_status_apr,
        "por_status_pcd": por_status_pcd,
        "por_tipo": por_tipo
    }


def fmt_dif(v):
    n = int(_num(v))
    return f"+{n}" if n > 0 else str(n)


def gerar_pdf_reportlab(obras):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            rightMargin=30, leftMargin=30,
                            topMargin=30, bottomMargin=30)
    
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        textColor=colors.HexColor('#1a3a5c'),
        spaceAfter=12
    )
    
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.gray,
        spaceAfter=20
    )

    agora = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
    elements.append(Paragraph("Relatório de Cotas – Jovens Aprendizes e PCDs", title_style))
    elements.append(Paragraph(f"Engenharia de Materiais Ltda – ENGEMAT | Gerado em: {agora} | Elaborado por: Altair Richard", subtitle_style))
    
    # Headers
    data = [[
        "Obra / Centro de Custo", "Tipo", "Func.", 
        "Nec. Apr", "Atual Apr", "Dif. Apr", "Status Apr",
        "Nec. PCD", "Atual PCD", "Dif. PCD", "Status PCD"
    ]]
    
    for o in obras:
        data.append([
            str(o.get('obra', '')),
            str(o.get('tipo', '')),
            str(int(_num(o.get('qtd_func')))),
            str(int(_num(o.get('nec_apr')))),
            str(int(_num(o.get('atual_apr')))),
            fmt_dif(o.get('def_apr')),
            str(o.get('status_apr', '')),
            str(int(_num(o.get('nec_pcd')))),
            str(int(_num(o.get('atual_pcd')))),
            fmt_dif(o.get('def_pcd')),
            str(o.get('status_pcd', ''))
        ])

    table = Table(data, colWidths=[200, 70, 40, 50, 50, 40, 75, 50, 50, 40, 75])
    
    # Estilos Base da Tabela
    ts = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a3a5c')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('ALIGN', (0,1), (0,-1), 'LEFT'),  # Obra alinhada à esquerda
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ])

    # Estilos Dinâmicos (Linhas Zebradas e Cores de Status)
    for i in range(1, len(data)):
        if i % 2 == 0:
            ts.add('BACKGROUND', (0,i), (-1,i), colors.HexColor('#F9FAFB'))
        
        # Cor Status Apr
        st_a = str(data[i][6]).lower()
        if 'abaixo' in st_a:
            ts.add('BACKGROUND', (6,i), (6,i), colors.HexColor('#FECACA'))
            ts.add('TEXTCOLOR', (6,i), (6,i), colors.HexColor('#991B1B'))
        
        # Cor Status PCD
        st_p = str(data[i][10]).lower()
        if 'abaixo' in st_p:
            ts.add('BACKGROUND', (10,i), (10,i), colors.HexColor('#FECACA'))
            ts.add('TEXTCOLOR', (10,i), (10,i), colors.HexColor('#991B1B'))

    table.setStyle(ts)
    elements.append(table)
    
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes


# ─── Rotas Web ────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    if session.get('logged_in'):
        return redirect(url_for('painel'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        senha = request.form.get('senha')
        if senha == APP_PASSWORD:
            session.permanent = True
            session['logged_in'] = True
            return redirect(url_for('painel'))
        else:
            error = "Senha incorreta."
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/painel')
@login_required
def painel():
    obras = fetch_obras()
    stats = calcular_stats(obras)
    return render_template('painel.html', obras=obras, stats=stats)


@app.route('/relatorio')
@login_required
def relatorio():
    return render_template('relatorio.html')


# ─── Rotas de API ─────────────────────────────────────────────────────────────
@app.route('/api/obras', methods=['GET'])
@login_required
def api_obras():
    return jsonify(fetch_obras())


@app.route('/api/salvar', methods=['POST'])
@login_required
def api_salvar():
    try:
        dados = request.get_json()
        obras_raw = dados.get('obras', [])
        obras_clean = [clean_obra(o) for o in obras_raw]
        
        # Deletar tudo
        supabase.table('obras').delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        
        # Inserir em lotes
        BATCH = 50
        for i in range(0, len(obras_clean), BATCH):
            batch = obras_clean[i:i+BATCH]
            supabase.table('obras').insert(batch).execute()
            
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)})


@app.route('/api/preview-pdf', methods=['POST'])
@login_required
def api_preview_pdf():
    dados = request.get_json()
    session['obras_pdf'] = dados.get('obras', [])
    return jsonify({"ok": True})


@app.route('/relatorio-pdf', methods=['GET'])
@login_required
def relatorio_pdf():
    obras = session.get('obras_pdf', fetch_obras())
    agora = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
    
    # HTML identical to the desktop version for browser printing
    total_obras = len(obras)
    total_func = int(sum(_num(o.get('qtd_func')) for o in obras))
    apr_at = int(sum(_num(o.get('atual_apr')) for o in obras))
    pcd_at = int(sum(_num(o.get('atual_pcd')) for o in obras))
    pend_apr = sum(1 for o in obras if 'abaixo' in str(o.get('status_apr','')).lower())
    pend_pcd = sum(1 for o in obras if 'abaixo' in str(o.get('status_pcd','')).lower())
    falta_apr = int(sum(abs(_num(o.get('def_apr'))) for o in obras if _num(o.get('def_apr')) < 0))
    falta_pcd = int(sum(abs(_num(o.get('def_pcd'))) for o in obras if _num(o.get('def_pcd')) < 0))

    def cor_status(s):
        s = str(s).lower()
        if 'abaixo' in s: return '#FECACA', '#991B1B', '🔴'
        if 'acima'  in s: return '#FEF08A', '#78350F', '🟡'
        return '#BBF7D0', '#14532D', '🟢'

    linhas = []
    for o in obras:
        bg_a, txt_a, ic_a = cor_status(o.get('status_apr',''))
        bg_p, txt_p, ic_p = cor_status(o.get('status_pcd',''))
        nome = str(o.get('obra','')).replace('<','&lt;').replace('>','&gt;')
        linhas.append(
            f'<tr>'
            f'<td class="tnome" title="{nome}">{nome}</td>'
            f'<td class="tc">{o.get("tipo","")}</td>'
            f'<td class="tc">{int(_num(o.get("qtd_func")))}</td>'
            f'<td class="tc">{int(_num(o.get("nec_apr")))}</td>'
            f'<td class="tc">{int(_num(o.get("atual_apr")))}</td>'
            f'<td class="tc bold" style="color:{txt_a}">{fmt_dif(o.get("def_apr"))}</td>'
            f'<td class="tc"><span class="badge" style="background:{bg_a};color:{txt_a}">{ic_a} {o.get("status_apr","")}</span></td>'
            f'<td class="tc">{int(_num(o.get("nec_pcd")))}</td>'
            f'<td class="tc">{int(_num(o.get("atual_pcd")))}</td>'
            f'<td class="tc bold" style="color:{txt_p}">{fmt_dif(o.get("def_pcd"))}</td>'
            f'<td class="tc"><span class="badge" style="background:{bg_p};color:{txt_p}">{ic_p} {o.get("status_pcd","")}</span></td>'
            f'</tr>'
        )
    tabela = '\n'.join(linhas)

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<title>Relatório de Cotas – {agora}</title>
<style>
  @page{{size:A4 landscape;margin:1.5cm}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',Arial,sans-serif;font-size:10pt;color:#1a1a1a;background:#fff;padding:28px}}
  .header{{display:flex;align-items:center;justify-content:space-between;border-bottom:3px solid #1a3a5c;padding-bottom:14px;margin-bottom:20px}}
  .header-left h1{{font-size:17pt;color:#1a3a5c;font-weight:700;line-height:1.2}}
  .header-left p{{font-size:9pt;color:#666;margin-top:4px}}
  .header-right{{text-align:right;font-size:9pt;color:#666}}
  .header-right strong{{display:block;font-size:11pt;color:#1a3a5c;margin-bottom:2px}}
  .cards{{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap}}
  .card{{flex:1 1 100px;border-radius:8px;padding:10px 14px;border-left:4px solid #1a3a5c;background:#F7F9FC}}
  .card.verm{{border-color:#EF4444;background:#FFF5F5}}
  .card .val{{font-size:22pt;font-weight:700;line-height:1;color:#1a3a5c}}
  .card.verm .val{{color:#EF4444}}
  .card .lbl{{font-size:8pt;color:#777;margin-top:2px}}
  table{{width:100%;border-collapse:collapse;font-size:8.5pt;margin-top:4px}}
  thead tr:first-child{{background:#1a3a5c;color:#fff}}
  thead tr:last-child{{background:#254d78;color:#fff}}
  thead th{{padding:7px 6px;text-align:center;font-weight:600;white-space:nowrap}}
  .gapr{{background:#154360}}
  .gpcd{{background:#14532d}}
  tbody tr{{border-bottom:1px solid #e5e7eb}}
  tbody tr:nth-child(even){{background:#F9FAFB}}
  td{{padding:5px 6px;vertical-align:middle}}
  td.tnome{{text-align:left;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:500}}
  td.tc{{text-align:center}}
  td.bold{{font-weight:700}}
  .badge{{display:inline-block;padding:2px 7px;border-radius:9px;font-size:8pt;font-weight:600;white-space:nowrap}}
  .footer{{margin-top:18px;border-top:1px solid #ddd;padding-top:8px;display:flex;justify-content:space-between;font-size:8pt;color:#999}}
  .legenda{{display:flex;gap:16px;font-size:8pt;margin-bottom:12px;align-items:center}}
  .dot{{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:3px}}
  .btn-print{{position:fixed;bottom:24px;right:24px;padding:10px 22px;background:#1a3a5c;color:#fff;border:none;border-radius:8px;font-size:11pt;cursor:pointer;font-family:inherit;box-shadow:0 4px 12px rgba(0,0,0,.2)}}
  @media print{{.btn-print{{display:none}}body{{padding:0}}}}
</style>
</head>
<body>

<button class="btn-print" onclick="window.print()">🖨️ Salvar como PDF</button>

<div class="header">
  <div class="header-left">
    <h1>📊 Relatório de Cotas – Jovens Aprendizes e PCDs</h1>
    <p>Engenharia de Materiais Ltda – ENGEMAT &nbsp;|&nbsp; Cota de referência: <strong>5%</strong> &nbsp;|&nbsp; Elaborado por: <strong>Altair Richard</strong></p>
  </div>
  <div class="header-right">
    <strong>{agora}</strong>
  </div>
</div>

<div class="cards">
  <div class="card"><div class="val">{total_obras}</div><div class="lbl">Obras / CCs</div></div>
  <div class="card"><div class="val">{total_func}</div><div class="lbl">Total Funcionários</div></div>
  <div class="card"><div class="val">{apr_at}</div><div class="lbl">Aprendizes Ativos</div></div>
  <div class="card"><div class="val">{pcd_at}</div><div class="lbl">PCDs Ativos</div></div>
  <div class="card verm"><div class="val">{pend_apr}</div><div class="lbl">Obras c/ pendência – Aprendiz</div></div>
  <div class="card verm"><div class="val">{pend_pcd}</div><div class="lbl">Obras c/ pendência – PCD</div></div>
  <div class="card verm"><div class="val">{falta_apr}</div><div class="lbl">Vagas em falta – Aprendiz</div></div>
  <div class="card verm"><div class="val">{falta_pcd}</div><div class="lbl">Vagas em falta – PCD</div></div>
</div>

<div class="legenda">
  <span><span class="dot" style="background:#EF4444"></span> Abaixo da cota</span>
  <span><span class="dot" style="background:#22C55E"></span> Dentro da cota</span>
  <span><span class="dot" style="background:#F59E0B"></span> Acima da cota</span>
</div>

<table>
  <thead>
    <tr>
      <th rowspan="2" style="text-align:left;min-width:180px">Obra / Centro de Custo</th>
      <th rowspan="2">Tipo</th>
      <th rowspan="2">Func.</th>
      <th colspan="4" class="gapr">🎓 JOVEM APRENDIZ</th>
      <th colspan="4" class="gpcd">♿ PCD</th>
    </tr>
    <tr>
      <th class="gapr">Necessário</th><th class="gapr">Atual</th>
      <th class="gapr">Diferença</th><th class="gapr">Status</th>
      <th class="gpcd">Necessário</th><th class="gpcd">Atual</th>
      <th class="gpcd">Diferença</th><th class="gpcd">Status</th>
    </tr>
  </thead>
  <tbody>
{tabela}
  </tbody>
</table>

<div class="footer">
  <span>{total_obras} obras listadas &nbsp;|&nbsp; Gerado em {agora}</span>
  <span>Engenharia de Materiais Ltda – ENGEMAT &nbsp;|&nbsp; Desenvolvido por Altair Richard</span>
</div>

</body>
</html>"""
    return html


@app.route('/api/enviar-email', methods=['POST'])
@login_required
def api_enviar_email():
    try:
        dados = request.get_json()
        email = dados.get('email')
        assunto = dados.get('assunto', 'Relatório de Cotas – ENGEMAT')
        obras = dados.get('obras', [])
        
        if not email:
            return jsonify({"ok": False, "erro": "E-mail de destino não fornecido."})
            
        pdf_bytes = gerar_pdf_reportlab(obras)
        
        params = {
            "from": EMAIL_FROM,
            "to": [email],
            "subject": assunto,
            "html": "<p>Olá,</p><p>Segue em anexo o relatório de acompanhamento de cotas de Jovens Aprendizes e PCDs.</p><br><p>Atenciosamente,<br><b>Portal de Cotas ENGEMAT</b></p>",
            "attachments": [
                {
                    "filename": "Relatorio_Cotas_ENGEMAT.pdf",
                    "content": list(pdf_bytes)  # Resend requires a list of integers for bytes
                }
            ]
        }
        
        email_response = resend.Emails.send(params)
        return jsonify({"ok": True, "id": email_response.get("id")})
        
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
