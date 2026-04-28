# dash_08.py
import dash
from dash import dcc, html, Input, Output, State, ALL, ctx
import dash_bootstrap_components as dbc
from datetime import datetime
import json
import uuid
import pandas as pd
from app_34 import process_query, execute_query, get_indicator_filters_for_display
import re

UI_GENERIC_ERROR = "Data is not available, we are adding the products. Try again later."
CHAT_SESSIONS = {}

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
    ],
    suppress_callback_exceptions=True,
    routes_pathname_prefix='/sql-search/',
    requests_pathname_prefix='/sql-search/',
    title="MoSPI AI Analytics"
)

SIDEBAR_STYLE = {
    'position': 'fixed', 'top': 0, 'left': 0, 'bottom': 0, 'width': '280px',
    'padding': '12px 0px', 'background': '#f7f7f8', 'borderRight': '1px solid #e0e0e0',
    'overflowY': 'auto', 'overflowX': 'hidden'
}
CONTENT_STYLE = {
    'marginLeft': '280px', 'padding': '0px', 'background': '#ffffff',
    'minHeight': '100vh', 'display': 'flex', 'flexDirection': 'column'
}
INPUT_CONTAINER_STYLE = {
    'position': 'fixed', 'bottom': 0, 'left': '280px', 'right': 0,
    'background': '#ffffff', 'padding': '20px 24px', 'borderTop': '1px solid #e0e0e0',
    'boxShadow': '0 -2px 10px rgba(0,0,0,0.05)'
}
USER_MESSAGE_STYLE = {
    'background': '#f0f0f0', 'color': '#1a1a1a', 'padding': '14px 18px',
    'borderRadius': '18px', 'marginBottom': '16px', 'maxWidth': '85%',
    'marginLeft': 'auto', 'wordWrap': 'break-word', 'wordBreak': 'keep-all',
    'whiteSpace': 'pre-wrap', 'fontSize': '15px', 'lineHeight': '1.5',
    'boxShadow': '0 1px 2px rgba(0,0,0,0.05)', 'minWidth': 'fit-content'
}
BOT_MESSAGE_STYLE = {
    'background': '#ffffff', 'color': '#1a1a1a', 'padding': '20px',
    'borderRadius': '12px', 'marginBottom': '16px', 'maxWidth': '100%', 'width': '100%',
    'boxSizing': 'border-box', 'overflow': 'hidden', 'border': '1px solid #e0e0e0',
    'wordWrap': 'break-word', 'fontSize': '15px', 'lineHeight': '1.6',
    'boxShadow': '0 1px 3px rgba(0,0,0,0.08)'
}
ERROR_STYLE = {
    'background': '#fff4f4', 'color': '#d32f2f', 'padding': '16px 20px',
    'borderRadius': '12px', 'marginBottom': '16px', 'border': '1px solid #ffcdd2',
    'fontSize': '15px', 'lineHeight': '1.5', 'boxShadow': '0 1px 3px rgba(211,47,47,0.1)'
}

CUSTOM_CSS = """
<style>
.option-select-btn:hover {
    transform: translateY(-4px) scale(1.02) !important;
    box-shadow: 0 8px 24px rgba(25,118,210,0.25) !important;
    border-color: #1565c0 !important;
    background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%) !important;
}

/* ── Editable SQL textarea ── */
.sql-editable {
    font-family: 'Fira Mono', Consolas, 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.65;
    width: 100%;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 12px 14px;
    resize: vertical;
    min-height: 80px;
    box-sizing: border-box;
    background: #f7f8fa;
    color: #1a1a1a;
    outline: none;
    transition: border-color 0.15s, box-shadow 0.15s;
}
.sql-editable:focus {
    border-color: #9e9e9e;
    box-shadow: 0 0 0 3px rgba(0,0,0,0.05);
    background: #ffffff;
}

/* ── Run Query button ── */
.run-sql-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 9px 22px;
    font-size: 13.5px;
    font-weight: 600;
    letter-spacing: 0.15px;
    color: #fff;
    background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
    border: none;
    border-radius: 10px;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(26,35,126,0.28), inset 0 1px 0 rgba(255,255,255,0.12);
    transition: background 0.18s, box-shadow 0.18s, transform 0.12s;
    position: relative;
    overflow: hidden;
}
.run-sql-btn::after {
    content: '';
    position: absolute; inset: 0;
    background: rgba(255,255,255,0);
    transition: background 0.15s;
}
.run-sql-btn:hover {
    background: linear-gradient(135deg, #283593 0%, #3949ab 100%);
    box-shadow: 0 4px 16px rgba(26,35,126,0.38), inset 0 1px 0 rgba(255,255,255,0.15);
    transform: translateY(-1px);
}
.run-sql-btn:hover::after { background: rgba(255,255,255,0.04); }
.run-sql-btn:active { transform: translateY(0); box-shadow: 0 1px 4px rgba(26,35,126,0.2); }
.run-sql-btn svg { flex-shrink: 0; opacity: 0.9; }

/* ── Schema button ── */
.schema-btn {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 9px 18px;
    font-size: 13.5px;
    font-weight: 500;
    letter-spacing: 0.1px;
    color: #37474f;
    background: #ffffff;
    border: 1.5px solid #cfd8dc;
    border-radius: 10px;
    cursor: pointer;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    transition: background 0.15s, border-color 0.15s, box-shadow 0.15s, transform 0.12s;
}
.schema-btn:hover {
    background: #f5f7fa;
    border-color: #90a4ae;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    transform: translateY(-1px);
}
.schema-btn:active { transform: translateY(0); }

/* ── Error box ── */
.sql-error-box {
    background: #fff8f8;
    border: 1px solid #ffcdd2;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    color: #c62828;
    margin-top: 10px;
}
.sql-error-hint { margin-top: 4px; font-size: 12px; color: #e65100; }

/* ── Schema modal table ── */
.schema-table { border-collapse: collapse; width: 100%; font-size: 13px; }
.schema-table thead th {
    background: #1a237e; color: #fff;
    padding: 10px 14px; text-align: left;
    font-size: 11px; font-weight: 700;
    letter-spacing: 0.5px; text-transform: uppercase;
    position: sticky; top: 0;
}
.schema-table tbody td {
    padding: 8px 14px;
    border-bottom: 1px solid #f0f0f0;
    vertical-align: top;
    line-height: 1.5;
}
.schema-table tbody tr:last-child td { border-bottom: none; }
.schema-table tbody tr:nth-child(even) td { background: #fafafa; }
.schema-col-name { font-weight: 600; color: #1a237e; white-space: nowrap; width: 160px; }
.schema-col-vals { color: #424242; }
</style>
"""


def create_chat_session():
    session_id = str(uuid.uuid4())
    CHAT_SESSIONS[session_id] = {
        'id': session_id, 'title': 'New Chat', 'messages': [],
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    return session_id


def get_session_title(messages):
    if messages:
        first_msg = next((m for m in messages if m['role'] == 'user'), None)
        if first_msg:
            return first_msg['content'][:45] + ('...' if len(first_msg['content']) > 45 else '')
    return 'New Chat'


def format_table_html(df):
    if df.empty:
        return "<p style='color:#757575;font-style:italic;'>No data available</p>"
    s = (
        "<div style='width:100%;max-width:100%;box-sizing:border-box;overflow-x:auto;"
        "overflow-y:auto;max-height:320px;border:1px solid #e0e0e0;border-radius:8px;display:block;'>"
        "<table style='min-width:max-content;border-collapse:collapse;font-size:14px;"
        "background:#ffffff;table-layout:auto;'>"
        "<thead><tr style='background:#f5f5f5;border-bottom:2px solid #e0e0e0;"
        "position:sticky;top:0;z-index:1;'>"
    )
    for col in df.columns:
        s += (f"<th style='padding:12px 16px;text-align:left;color:#1a1a1a;font-weight:600;"
              f"border-bottom:2px solid #1976d2;background:#f5f5f5;white-space:nowrap;'>"
              f"{col.replace('_',' ').title()}</th>")
    s += "</tr></thead><tbody>"
    for idx, row in df.iterrows():
        bg = '#fafafa' if idx % 2 == 0 else '#ffffff'
        s += f"<tr style='background:{bg};border-bottom:1px solid #e0e0e0;'>"
        for val in row:
            s += f"<td style='padding:10px 16px;color:#424242;white-space:nowrap;'>{val}</td>"
        s += "</tr>"
    s += f"</tbody></table></div><p style='font-size:12px;color:#9e9e9e;margin-top:6px;'>{len(df)} rows</p>"
    return s


def build_schema_table(filters_meta):
    """Returns a Dash html.Table for the schema modal."""
    if not filters_meta:
        return html.P("No metadata available.", style={'color': '#757575', 'fontStyle': 'italic'})
    rows = []
    for col, vals in filters_meta.items():
        rows.append(html.Tr([
            html.Td(
                col.replace('_', ' ').title(),
                className='schema-col-name',
                style={'borderRight': '1px solid #e0e0e0'}  # 👈 vertical separator
            ),
            html.Td(
                ', '.join(str(v) for v in vals),
                className='schema-col-vals'
            )
        ]))
    return html.Div(
        html.Table([
            html.Thead(html.Tr([
            html.Th("Column", style={'borderRight': '1px solid #e0e0e0'}),
            html.Th("Distinct Values")
        ])),
            html.Tbody(rows)
        ], className='schema-table'),
        style={'overflowY': 'auto', 'maxHeight': '420px'}
    )


def make_sql_block(msg_index, sql_query, filters_meta):
    """
    Editable SQL textarea ABOVE the results table, plus:
      - Run Query button (modern gradient)
      - Show Schema button (opens modal)
    No schema data rendered in DOM until modal opens.
    """
    schema_table = build_schema_table(filters_meta)

    return html.Div([
        # Small label
        html.Div("Generated SQL", style={
            'fontSize': '11px', 'fontWeight': '600', 'color': '#9e9e9e',
            'textTransform': 'uppercase', 'letterSpacing': '0.5px', 'marginBottom': '6px'
        }),

        # Editable SQL textarea
        dbc.Textarea(
            id={'type': 'edit-sql-input', 'index': msg_index},
            value=sql_query,
            className='sql-editable',
            rows=4
        ),

        # Action row: Run + Show Schema
        html.Div([
            html.Button(
                "▶  Run Query",
                id={'type': 'run-sql-btn', 'index': msg_index},
                n_clicks=0,
                style={
                    "backgroundColor": "#ffffff",
                    "border": "1px solid #e0e0e0",
                    "color": "#333",
                    "padding": "8px 18px",
                    "borderRadius": "8px",
                    "fontSize": "13px",
                    "cursor": "pointer"
                }
            ),

            html.Button(
                "⊞  Show Schema",
                id={'type': 'schema-btn', 'index': msg_index},
                n_clicks=0,
                style={
                    "backgroundColor": "#ffffff",
                    "border": "1px solid #e0e0e0",
                    "color": "#333",
                    "padding": "8px 18px",
                    "borderRadius": "8px",
                    "fontSize": "13px",
                    "cursor": "pointer"
                }
            )
        ],
        style={
            "display": "flex",
            "gap": "10px",
            "marginTop": "16px"   
        }),

        # Schema modal (hidden by default)
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Schema — Column & Distinct Values"),
                            style={'background': '#f5f7fa'}),
            dbc.ModalBody(schema_table, style={'padding': '0'}),
            dbc.ModalFooter(
                dbc.Button("Close", id={'type': 'schema-close', 'index': msg_index},
                           className="ms-auto",
                           style={'background': '#1a237e', 'border': 'none',
                                  'borderRadius': '8px', 'fontWeight': '600'})
            )
        ], id={'type': 'schema-modal', 'index': msg_index},
           is_open=False, size="lg", scrollable=True),

        # Result area
        html.Div(id={'type': 'edit-sql-result', 'index': msg_index}, style={'marginTop': '14px'})

    ])


def create_sidebar():
    return html.Div([
        html.Div([
            html.Img(),
            html.Hr(),
            html.Div(
                dbc.Button(
                    [html.I(className='fas fa-plus', style={'marginRight': '8px'}), 'New Chat'],
                    id='new-chat-btn',
                    style={
                        'width': '100%', 'borderRadius': '8px',
                        'background': 'linear-gradient(90deg, #0A266C 0%, #4265BA 100%)',
                        'color': '#ffffff', 'fontSize': '16px', 'fontWeight': '600',
                        'padding': '8px 0px', 'border': 'none', 'cursor': 'pointer'
                    }
                ),
                id='new-chat-btn-wrapper',
                style={"padding": "0px 12px", "backgroundColor": "#f5f5f5",
                       "borderRadius": "12px", "marginBottom": "16px"}
            )
        ]),
        html.Hr(style={'borderColor': 'rgb(192 192 192)', 'margin': '10px 0', 'opacity': '1'}),
        html.Div([
            html.Div([
                html.Div(
                    html.H5("💭 Chat History", style={
                        'color': 'rgb(4 4 4)', 'fontSize': '14px', 'fontWeight': '600',
                        'textTransform': 'uppercase', 'letterSpacing': '0.5px',
                        'marginBottom': '16px', 'marginTop': '0px'
                    }),
                    className="chat-history-wrapper"
                ),
                html.Div([
                    html.Div([
                        html.Img(src="https://img.icons8.com/sf-black-filled/64/chat.png",
                                 style={"height": "48px", "width": "48px", "opacity": "0.2"}),
                        html.P("No conversations yet", style={
                            'color': '#333', 'fontSize': '16px', 'margin': '0',
                            'fontWeight': '500', "opacity": "0.6"
                        }),
                        html.P("Your queries will appear here", style={
                            'color': '#999', 'fontSize': '14px', "opacity": "0.6"
                        })
                    ], className="no-conversations-wrapper", style={"textAlign": "center"})
                ], id='session-list')
            ], className="chat-history-section"),
            html.Div(id='chat-history-list', style={'marginTop': '8px'})
        ], className="chat-history-parent",
            style={"padding": "10px 16px", "backgroundColor": "#f8f8f8", "borderRadius": "12px"}),
        dcc.Store(id='current-session-id'),
        dcc.Store(id='sessions-store', data={}),
        dcc.Store(id='product-name-store', data=''),
        dcc.Store(id='url-check-done', data=False)
    ], style=SIDEBAR_STYLE)


def create_chat_interface():
    return html.Div([
        dcc.Location(id='url', refresh=False),
        html.Div([
            html.H2("e-Sankhyiki Data Query AI Chatbot", style={
                'fontSize': '28px', 'fontWeight': '700', 'margin': '0',
                'lineHeight': '32px', 'color': '#000'
            }),
            html.P("Ask questions across Gender, Environment, Energy Stats, CPI, CPIALRL, HCES, TUS datasets",
                   style={'color': 'rgb(85,85,85)', 'fontSize': '14px', 'margin': '0'})
        ], style={
            'padding': '23px 25px', 'backgroundColor': '#ffffff',
            'boxShadow': '0 2px 8px rgba(0,0,0,0.1)',
            'borderBottom': '1px solid rgb(222,226,230)', 'textAlign': 'left'
        }),
        html.Div(id="chat-parent-container", style={
            "padding": "20px", "flex": "1", "overflowY": "auto",
            "marginBottom": "90px", "height": "calc(100vh - 224px)"
        }, children=[
            html.Div(id="messages-container", style={
                "padding": "50px 20px", "display": "flex", "flexDirection": "column",
                "alignItems": "center", "height": "100%", "justifyContent": "center"
            })
        ]),
        html.Div([
            dbc.InputGroup([
                dbc.Textarea(
                    id='user-input',
                    placeholder='Ask a question about your data...',
                    style={
                        'resize': 'none', 'background': '#ffffff', 'border': '1px solid #d0d0d0',
                        'color': '#1a1a1a', 'borderRadius': '12px', 'padding': '14px 18px',
                        'fontSize': '15px', 'minHeight': '56px', 'maxHeight': '200px',
                        'boxShadow': '0 2px 6px rgba(0,0,0,0.08)', 'transition': 'all 0.2s'
                    },
                    rows=1
                ),
                html.Div([
                    dcc.Loading(
                        id='loading-spinner', type='default',
                        children=html.Div(id='loading-output'), color='#1976d2',
                        style={'position': 'absolute', 'right': '60px', 'top': '50%',
                               'transform': 'translateY(-50%)', 'zIndex': '10'},
                        parent_style={'position': 'relative', 'display': 'inline-block'}
                    ),
                    dbc.Button([
                        html.Img(src="https://img.icons8.com/material-sharp/24/filled-sent.png",
                                 style={"width": "18px", "filter": "invert(1)"})
                    ], id='send-btn', n_clicks=0, style={
                        "borderRadius": "50%",
                        "background": "linear-gradient(90deg, #0A266C 0%, #4265BA 100%)",
                        "color": "#fff", "width": "50px", "height": "50px",
                        "display": "flex", "justifyContent": "center", "alignItems": "center",
                        "border": "none", "padding": "0",
                        "boxShadow": "0 2px 6px rgba(0,0,0,0.2)", "transition": "all 0.2s"
                    })
                ], style={'position': 'relative', 'display': 'flex', 'alignItems': 'center'})
            ], style={'width': '100%', 'maxWidth': '900px', 'margin': '0 auto',
                      'display': 'flex', 'alignItems': 'center', 'gap': '12px'})
        ], style=INPUT_CONTAINER_STYLE),
        dbc.Modal([
            dbc.ModalHeader("Enter URL Manually"),
            dbc.ModalBody([
                dbc.Input(id='manual-url-input', placeholder='Enter URL with product parameter',
                          type='text', style={'marginBottom': '10px'}),
                html.Div(id='url-error-msg', style={'color': 'red', 'fontSize': '14px'})
            ]),
            dbc.ModalFooter(
                dbc.Button("Submit", id='manual-url-submit', className="ms-auto", n_clicks=0)
            )
        ], id='url-modal', is_open=False)
    ], style=CONTENT_STYLE)


app.layout = html.Div([
    html.Div([dcc.Markdown(CUSTOM_CSS, dangerously_allow_html=True)]),
    create_sidebar(),
    create_chat_interface()
], style={'fontFamily': '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'})


# ─────────────────────────────────────────────────────────────
# Callbacks
# ─────────────────────────────────────────────────────────────
app.clientside_callback(
    "function(pathname) { return window.location.href; }",
    Output('product-name-store', 'data', allow_duplicate=True),
    Input('url', 'pathname'),
    prevent_initial_call=True
)


@app.callback(
    [Output('product-name-store', 'data'),
     Output('url-modal', 'is_open'),
     Output('url-check-done', 'data')],
    [Input('product-name-store', 'data'),
     Input('manual-url-submit', 'n_clicks')],
    [State('manual-url-input', 'value'),
     State('url-check-done', 'data')],
    prevent_initial_call=True
)
def extract_product_from_url(current_url, submit_clicks, manual_url, url_check_done):
    if url_check_done:
        return dash.no_update, dash.no_update, dash.no_update
    triggered_id = ctx.triggered_id
    if triggered_id == 'manual-url-submit' and manual_url:
        try:
            return manual_url.rstrip('/').split('/')[-1], False, True
        except:
            return '', False, True
    if current_url and isinstance(current_url, str):
        try:
            clean_url = current_url.rstrip('/')
            if '/sql-search/' in clean_url:
                product = clean_url.split('/sql-search/')[-1]
                if product:
                    return product, False, True
            return '', True, False
        except:
            return '', True, False
    return '', False, False


@app.callback(
    [Output('current-session-id', 'data'),
     Output('sessions-store', 'data'),
     Output('messages-container', 'children')],
    [Input('new-chat-btn', 'n_clicks')],
    [State('sessions-store', 'data')]
)
def create_new_chat(n_clicks, sessions_data):
    if n_clicks:
        session_id = create_chat_session()
        sessions_data = sessions_data or {}
        sessions_data[session_id] = CHAT_SESSIONS[session_id]
        return session_id, sessions_data, []
    if not sessions_data:
        session_id = create_chat_session()
        sessions_data = {session_id: CHAT_SESSIONS[session_id]}
        return session_id, sessions_data, []
    return dash.no_update, sessions_data, dash.no_update


@app.callback(
    Output('chat-history-list', 'children'),
    [Input('sessions-store', 'data'), Input('current-session-id', 'data')]
)
def update_chat_history(sessions_data, current_id):
    if not sessions_data:
        return []
    items = []
    for sid, session in sorted(sessions_data.items(), key=lambda x: x[1]['created_at'], reverse=True):
        is_active = sid == current_id
        items.append(dbc.Button(
            session['title'],
            id={'type': 'history-item', 'index': sid},
            style={
                'width': '100%', 'textAlign': 'left', 'borderRadius': '8px',
                'padding': '12px 14px', 'fontSize': '13px',
                'background': '#e3f2fd' if is_active else 'transparent',
                'border': '1px solid #90caf9' if is_active else '1px solid transparent',
                'color': '#1a1a1a', 'overflow': 'hidden', 'textOverflow': 'ellipsis',
                'whiteSpace': 'nowrap', 'fontWeight': '500' if is_active else '400',
                'transition': 'all 0.2s',
                'boxShadow': '0 1px 3px rgba(0,0,0,0.05)' if is_active else 'none'
            }
        ))
    return items


@app.callback(
    [Output('current-session-id', 'data', allow_duplicate=True),
     Output('messages-container', 'children', allow_duplicate=True)],
    [Input({'type': 'history-item', 'index': ALL}, 'n_clicks')],
    [State('sessions-store', 'data')],
    prevent_initial_call=True
)
def switch_chat(n_clicks, sessions_data):
    if not ctx.triggered or not any(n_clicks):
        return dash.no_update, dash.no_update
    session_id = json.loads(ctx.triggered[0]['prop_id'].split('.')[0])['index']
    messages = sessions_data.get(session_id, {}).get('messages', [])
    return session_id, render_messages(messages)


@app.callback(
    [Output('messages-container', 'children', allow_duplicate=True),
     Output('sessions-store', 'data', allow_duplicate=True),
     Output('user-input', 'value'),
     Output('loading-output', 'children')],
    [Input('send-btn', 'n_clicks'), Input('user-input', 'n_submit')],
    [State('user-input', 'value'),
     State('current-session-id', 'data'),
     State('sessions-store', 'data'),
     State('product-name-store', 'data')],
    prevent_initial_call=True
)
def send_message(send_clicks, submit, query, session_id, sessions_data, product_name):
    if not query or not query.strip():
        return dash.no_update, dash.no_update, dash.no_update, ""

    if not product_name:
        return render_messages([{
            'role': 'assistant',
            'content': '❌ Product name not detected. Please ensure URL contains product parameter.',
            'timestamp': datetime.now().strftime('%H:%M')
        }]), sessions_data, '', ""

    if not session_id:
        session_id = create_chat_session()
        sessions_data = sessions_data or {}
        sessions_data[session_id] = CHAT_SESSIONS[session_id]

    session = sessions_data[session_id]
    session['messages'].append({
        'role': 'user', 'content': query,
        'timestamp': datetime.now().strftime('%H:%M')
    })
    if len(session['messages']) == 1:
        session['title'] = get_session_title(session['messages'])

    sessions_data[session_id] = session

    try:
        response = process_query(query, product_name)
    except Exception as e:
        response = {'success': False, 'error': UI_GENERIC_ERROR, 'internal_error': str(e)}

    if response['success']:
        df = pd.DataFrame(response.get('rows', []), columns=response.get('columns', []))
        table_html = format_table_html(df)
        # SQL is NOT in the markdown string — it's rendered as an editable textarea via make_sql_block
        bot_message = (
            f"**Dataset:** {response['dataset']}  \n"
            f"**Indicator:** {response['indicator']}  \n"
            f"**Rows Found:** {response['row_count']}\n\n"
            f"**Results:**\n{table_html}"
        )
    else:
        if response.get('error_type') == 'DATASET_MISMATCH':
            bot_message = "❌ This question is not related to the current selected product. Please ask a question related to this product only."
        else:
            bot_message = UI_GENERIC_ERROR

    session['messages'].append({
        'role': 'assistant',
        'content': bot_message,
        'timestamp': datetime.now().strftime('%H:%M'),
        'raw_response': response
    })

    sessions_data[session_id] = session
    CHAT_SESSIONS[session_id] = session

    return render_messages(session['messages']), sessions_data, '', ""


# ─────────────────────────────────────────────────────────────
# Run edited SQL callback
# ─────────────────────────────────────────────────────────────
@app.callback(
    Output({'type': 'edit-sql-result', 'index': ALL}, 'children'),
    Input({'type': 'run-sql-btn', 'index': ALL}, 'n_clicks'),
    [State({'type': 'edit-sql-input', 'index': ALL}, 'value'),
     State('product-name-store', 'data')],
    prevent_initial_call=True
)
def run_edited_sql(n_clicks_list, sql_values, product_name):
    triggered = ctx.triggered_id
    if not triggered or not any(n for n in n_clicks_list if n):
        return [dash.no_update] * len(n_clicks_list)

    clicked_index = triggered['index']
    index_map = [ctx.inputs_list[0][i]['id']['index'] for i in range(len(n_clicks_list))]
    outputs = [dash.no_update] * len(n_clicks_list)
    pos = index_map.index(clicked_index) if clicked_index in index_map else None
    if pos is None:
        return outputs

    raw_sql = (sql_values[pos] or "").strip()
    if not raw_sql:
        outputs[pos] = html.Div("⚠️ SQL query is empty.",
                                 style={'color': '#e65100', 'fontSize': '13px'})
        return outputs

    # Enforce LIMIT 100
    clean_sql = re.sub(r';\s*$', '', raw_sql, flags=re.IGNORECASE).strip()
    clean_sql = re.sub(r'\bLIMIT\s+\d+\s*$', '', clean_sql, flags=re.IGNORECASE).strip()
    final_sql = clean_sql + " LIMIT 100;"

    try:
        result, db_error = execute_query(product_name, final_sql, timeout_seconds=60)
    except Exception as e:
        db_error = str(e)
        result = []

    if db_error:
        hint = ""
        if "column" in db_error.lower() and "does not exist" in db_error.lower():
            hint = "Check column names — they must match the schema exactly."
        elif "syntax error" in db_error.lower():
            hint = "Check your SQL syntax."
        elif "timed out" in db_error.lower() or "timeout" in db_error.lower():
            hint = "Query exceeded 60 seconds. Try narrowing your filters."
        elif "relation" in db_error.lower() and "does not exist" in db_error.lower():
            hint = "Use 'data_view' as the table name."

        outputs[pos] = html.Div([
            html.Div(f"Error: {db_error}", className='sql-error-box'),
            html.Div(hint, className='sql-error-hint') if hint else None
        ])
    else:
        df = pd.DataFrame(result)
        table_html = format_table_html(df)
        outputs[pos] = dcc.Markdown(table_html, dangerously_allow_html=True)

    return outputs


# ─────────────────────────────────────────────────────────────
# Schema modal open / close
# ─────────────────────────────────────────────────────────────
@app.callback(
    Output({'type': 'schema-modal', 'index': ALL}, 'is_open'),
    [Input({'type': 'schema-btn', 'index': ALL}, 'n_clicks'),
     Input({'type': 'schema-close', 'index': ALL}, 'n_clicks')],
    State({'type': 'schema-modal', 'index': ALL}, 'is_open'),
    prevent_initial_call=True
)
def toggle_schema_modal(open_clicks, close_clicks, is_open_states):
    triggered = ctx.triggered_id
    if not triggered:
        return [dash.no_update] * len(is_open_states)

    t_type = triggered.get('type')
    t_index = triggered.get('index')

    # Find which modal matches
    # We need to map index to position in the ALL lists
    # Use ctx.inputs_list to get the index order
    open_ids  = [ctx.inputs_list[0][i]['id']['index'] for i in range(len(open_clicks))]
    close_ids = [ctx.inputs_list[1][i]['id']['index'] for i in range(len(close_clicks))]
    modal_ids = [ctx.states_list[0][i]['id']['index'] for i in range(len(is_open_states))]

    outputs = list(is_open_states)
    if t_index in modal_ids:
        pos = modal_ids.index(t_index)
        if t_type == 'schema-btn':
            outputs[pos] = True
        elif t_type == 'schema-close':
            outputs[pos] = False
    return outputs


# ─────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────
def render_messages(messages):
    if not messages:
        return html.Div([
            html.Div([
                html.Div(
                    html.Img(src="https://img.icons8.com/fluency/48/chatbot--v1.png",
                             style={"width": "64px", "height": "64px", "marginBottom": "12px"}),
                    style={"textAlign": "center"}
                ),
                html.H2("I am your e-Sankhyiki Data Query Assistant", style={
                    "textAlign": "center", "marginBottom": "6px", "fontWeight": "700",
                    "fontSize": "24px", "color": "#1a1a1a"
                }),
                html.P("Ask questions in natural language. Get tables, charts, insights & explanations instantly.",
                       style={"textAlign": "center", "color": "#555", "fontSize": "14px",
                              "marginBottom": "18px", "lineHeight": "1.6", "maxWidth": "520px",
                              "marginLeft": "auto", "marginRight": "auto"})
            ], style={"textAlign": "center"})
        ])

    rendered = []
    for msg_index, msg in enumerate(messages):
        if msg['role'] == 'user':
            rendered.append(html.Div([
                html.Div(msg['content'], style=USER_MESSAGE_STYLE),
                html.Div(msg['timestamp'], style={
                    'fontSize': '11px', 'color': '#9e9e9e', 'textAlign': 'right',
                    'marginTop': '6px', 'marginRight': '4px'
                })
            ], style={'marginBottom': '24px'}))
        else:
            content = msg['content']
            is_error = content.startswith('❌')
            raw_response = msg.get('raw_response', {})
            sql_for_edit = raw_response.get('sql') if raw_response.get('success') else None
            filters_meta = raw_response.get('filters_meta', {}) if raw_response.get('success') else {}

            msg_children = []

            # SQL editable block FIRST (above results), only for successful responses
            if sql_for_edit and not is_error:
                msg_children.append(make_sql_block(msg_index, sql_for_edit, filters_meta))

            # Then the bot message (which contains Dataset/Indicator/Results table)
            msg_children.append(
                html.Div(
                    dcc.Markdown(content, dangerously_allow_html=True,
                                 style={'margin': 0, 'color': '#1a1a1a'}),
                    style=ERROR_STYLE if is_error else BOT_MESSAGE_STYLE
                )
            )
            msg_children.append(
                html.Div(msg['timestamp'], style={
                    'fontSize': '11px', 'color': '#9e9e9e', 'marginTop': '6px', 'marginLeft': '4px'
                })
            )

            rendered.append(html.Div(msg_children, style={
                'marginBottom': '24px', 'width': '100%', 'maxWidth': '100%', 'overflow': 'hidden'
            }))

    return rendered


if __name__ == '__main__':
    app.run(debug=False, port=5020)

    