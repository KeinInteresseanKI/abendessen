import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title='SPEISEPLAN', page_icon='🍽️')

credentials_info = st.secrets["gcp_service_account"]

scope = ['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive']

credentials = Credentials.from_service_account_info(credentials_info, scopes=scope)
gc = gspread.authorize(credentials)

spreadsheet_name = "abendessen" # ⬅️ Google Sheetsの名前入れる
try:
    sh = gc.open(spreadsheet_name)
    worksheet = sh.worksheet("abendessen") # ⬅️ ワークシートの名前入れる
except gspread.exceptions.SpreadsheetNotFound:
    st.error(f'{spreadsheet_name} nicht gefunden!')
    st.stop()
except gspread.exceptions.WorksheetNotFound:
    st.error("Worksheet 'abendessen' nicht gefunden!") # ⬅️ ワークシートの名前入れる
    st.stop()

@st.cache_data(ttl=5)
def load_df():
    data = worksheet.get_all_values()

    if not data or not any(row for row in data):
        return pd.DataFrame(columns=['date','Speise01','Speise02','Speise03','Speise04','Speise05', 'Datum', 'Wochentag'])

    headers = data[0]
    df = pd.DataFrame(data[1:], columns=headers)

    required_cols = ['date','Speise01','Speise02','Speise03','Speise04','Speise05']
    if not all(col in df.columns for col in required_cols):
        st.warning('In der Kopfzeile der Tabelle wurden die erforderlichen Spalten nicht gefunden.') # ⬅️ ここテキスト入れる
        return pd.DataFrame(columns=required_cols)

    df = df[required_cols]

    # ここが変更点: dfの行数が0でない場合のみ日付処理を行う
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        weekday_map = {
            'Mon':'Mo','Tue':'Di','Wed':'Mi','Thu':'Do','Fri':'Fr',
            'Sat':'Sa','Sun':'So',
        }
        df['Wochentag'] = df['date'].dt.strftime('%a').map(weekday_map).fillna('')
        df['Datum'] = df['date'].dt.strftime('%d.%m.%Y').fillna('') + ' ' + df['Wochentag']
    else:
        # dfが空の場合でも、'Datum'列と'Wochentag'列を追加しておく
        df['Wochentag'] = ''
        df['Datum'] = ''

    return df

def update_gsheet_and_rerun(df_to_write):
    df_for_gsheet = df_to_write.copy()

    # Google Sheetsを更新する前にDataFrameを日付順に並べ替え
    df_for_gsheet.sort_values(by='date', ascending=True, inplace=True)

    # 13ヶ月以上のデータを削除するコード
    today = pd.Timestamp('today')
    cutoff_date = today - pd.Timedelta(days=397)
    #df_for_gsheet['date'] = pd.to_datetime(df_for_gsheet['date'], errors='coerce')
    df_for_gsheet = df_for_gsheet[df_for_gsheet['date']>= cutoff_date].reset_index(drop=True)
    # 13ヶ月以上のデータを削除するコード（終わり）

    df_for_gsheet = df_for_gsheet.fillna("")

    df_for_gsheet['date'] = df_for_gsheet['date'].apply(lambda x: x.isoformat() if isinstance(x, datetime.date) or isinstance(x, pd.Timestamp) else x)

    # Google Sheetsに書き込む前に、不要な列（Datum, Wochentag）を削除
    if 'Datum' in df_for_gsheet.columns:
        df_for_gsheet = df_for_gsheet.drop('Datum', axis=1)
    if 'Wochentag' in df_for_gsheet.columns:
        df_for_gsheet = df_for_gsheet.drop('Wochentag', axis=1)

    data_to_write = [df_for_gsheet.columns.tolist()] + df_for_gsheet.values.tolist()

    worksheet.clear()
    worksheet.update(data_to_write)

    st.cache_data.clear()
    st.rerun()

def add_item(datum,i01,i02,i03,i04,i05):
    df = load_df()
    new_row = pd.DataFrame([[pd.Timestamp(datum), i01, i02, i03, i04, i05]], columns=['date', 'Speise01', 'Speise02', 'Speise03', 'Speise04', 'Speise05'])
    update_df = pd.concat([df,new_row], ignore_index=True)

    update_gsheet_and_rerun(update_df)
        
# UI部分

df = load_df()
st.header('🍽️ SPEISEPLAN')

mode = st.radio('Mode auswählen',['Speiseplan der Woche',
                                  'Neuer Speiseplan / Änderung',
                                  'Speise vor einem Jahr - für 2 M.',
                                  'Datumssuche nach Speise'], horizontal=True)

if mode == 'Speiseplan der Woche':
    df = load_df()
    # 今日のおかず一覧

    today = datetime.date.today()
    today_ts = pd.Timestamp(today)
    heute = today.strftime("%d.%m.%Y")
    st.write(f'##### 🥗 Speise von heute: {heute}')

    # .dt accessorを使用する前に、'date'列がdatetime型であることを再確認
    if not pd.api.types.is_datetime64_any_dtype(df['date']):
        df['date'] = pd.to_datetime(df['date'], errors='coerce')

    today_df = df[df['date'].notna() & (df['date'].dt.normalize() == today_ts)]

    if today_df.empty:
        st.info(f'Noch keinen Speiseplan vom {heute}')
    else:
        for i, row in today_df.iterrows():
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.write(f'###### {row['Speise01']}')
            with col2:
                st.write(f'###### {row['Speise02']}')
            with col3:
                st.write(f'###### {row['Speise03']}')
            with col4:
                st.write(f'###### {row['Speise04']}')
            with col5:
                st.write(f'###### {row['Speise05']}')

    st.markdown('---')
    today = pd.Timestamp('today').normalize()
    to_day = today - pd.Timedelta(days=1)
    tag_in_7 = today + pd.Timedelta(days=7)

    df = df[(df['date'] >= to_day) & (df['date'] <= tag_in_7)]

    df.sort_values(by='date', ascending=True, inplace=True)

    st.write('##### 🥗 Speise für diese Woche')
    st.dataframe(df[['Datum', 'Speise01', 'Speise02', 'Speise03', 'Speise04', 'Speise05']], hide_index=True)

elif mode == 'Neuer Speiseplan / Änderung':
    # おかず入力部分
    # 日付 を入力

    df = load_df()

    # フォームの送信状態と確認待ち状態を管理するセッションステートを初期化
    # if "form_submitted" not in st.session_state:
    #     st.session_state.form_submitted = False
    if "confirm_pending" not in st.session_state:
        st.session_state.confirm_pending = False
    if "input_data_to_confirm" not in st.session_state:
        st.session_state.input_data_to_confirm = {}


    st.write('##### 🥘 Was kommt als Nächstes? Plan den neuen Tag!')
    if not st.session_state.confirm_pending:
        datum = st.date_input('Datum:', value=None ,format="DD.MM.YYYY", key="add_date_input")

        if datum:
            try:
                date_object = datum
            except ValueError:
                st.text('Ungültiges Datumformat. Format -> dd.mm.yyyy')
            except Exception as e:
                st.text(f'Fehlmeldung: {e}')

        # 日付を入力　Ende

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            item01 = st.text_input('Speise01:', key="add_item01_input")
        with col2:
            item02 = st.text_input('Speise02:', key="add_item02_input")
        with col3:
            item03 = st.text_input('Speise03:', key="add_item03_input")
        with col4:
            item04 = st.text_input('Speise04:', key="add_item04_input")
        with col5:
            item05 = st.text_input('Speise05:', key="add_item05_input")

    # おかず入力部分（終わり）

        # 追加ボタン（押されたら確認待ち状態へ）
        if st.button("🥢 Hinzufügen", key='add_button') and datum and item01:
            # 入力内容をセッションステートに保存
            st.session_state.input_data_to_confirm = {
                "datum": datum,
                "item01": item01,
                "item02": item02,
                "item03": item03,
                "item04": item04,
                "item05": item05,
            }
            st.session_state.confirm_pending = True # 確認待ち状態にする
            st.rerun() # 確認画面を表示するためにリラン

    # 確認待ち状態の場合、確認メッセージとボタンを表示
    elif st.session_state.confirm_pending:
        st.markdown(
            '<p style="font-size:20px; font-weight: bold; color: red;">'
            'Eingabe richtig?'
            '</p>',
            unsafe_allow_html=True
        )
        # 保存しておいた入力内容を表示
        data_to_confirm = st.session_state.input_data_to_confirm
        st.write(f'Datum: {data_to_confirm["datum"]}')
        st.write(f'Speise01: {data_to_confirm["item01"]}')
        st.write(f'Speise02: {data_to_confirm["item02"]}')
        st.write(f'Speise03: {data_to_confirm["item03"]}')
        st.write(f'Speise04: {data_to_confirm["item04"]}')
        st.write(f'Speise05: {data_to_confirm["item05"]}')

        col1, col2, col3 = st.columns(3)
        with col1:
            # はい（追加）ボタン
            if st.button('👍 Ja', key='confirm_yes_button'):
                # データ追加処理を実行
                add_item(data_to_confirm["datum"],
                         data_to_confirm["item01"],
                         data_to_confirm["item02"],
                         data_to_confirm["item03"],
                         data_to_confirm["item04"],
                         data_to_confirm["item05"])
                st.session_state.confirm_pending = False # 確認待ち状態を解除
                st.session_state.form_submitted = True # 送信完了状態にする
                st.session_state.input_data_to_confirm = {} # 保存した入力内容をクリア
                st.rerun()
                # データ追加処理の中でst.rerun()が呼ばれるのでここでは不要

        with col2:
            # Zurück ボタン
            if st.button('↩️ Zurück', key='confirm_back_to_start_button'):
                st.session_state.confirm_pending = False # 確認待ち状態を解除
                st.session_state.input_data_to_confirm = {} # 保存した入力内容をクリア
                st.session_state.mode_index = 0 # Speiseplan der Wocheに戻る
                st.rerun()

        with col3:
            # いいえ（キャンセル）ボタン
            if st.button('👋 Nein', key='confirm_no_button'):
                st.session_state.confirm_pending = False # 確認待ち状態を解除
                st.session_state.input_data_to_confirm = {} # 保存した入力内容をクリア
                st.rerun() # 入力画面に戻るためにリラン   

    st.markdown('---')
    st.write('##### Änderung: Speiseplan der Woche')
    st.info('Zum Ändern: Tippe auf eine Zelle, gib eine neue Speise ein und bestätige mit „👍 Ändern“')

    today = pd.Timestamp('today').normalize()
    to_day = today - pd.Timedelta(days=1)
    tag_in_7 = today + pd.Timedelta(days=7)

    # 1週間分のデータをフィルタリング
    df_this_week = df[(df['date'] >= to_day) & (df['date'] <= tag_in_7)].copy()
    df_this_week.sort_values(by='date', ascending=True, inplace=True)
    df_this_week_for_display = df_this_week[['Datum', 'Speise01', 'Speise02', 'Speise03', 'Speise04', 'Speise05']]

    # st.data_editor を使って表示し、編集されたデータを取得
    edited_df_this_week = st.data_editor(df_this_week_for_display, hide_index=True)

    # 編集後のデータフレームから元のDataFrameを再構築する
    # 'Datum'列から日付情報を抽出してdate列を更新する
    edited_df_this_week['date'] = pd.to_datetime(edited_df_this_week['Datum'].str.split(' ').str[0], format='%d.%m.%Y', errors='coerce')

    # 元のdfから今週のデータを削除し、編集後のデータを結合する
    df_without_this_week = df[(df['date'] < to_day) | (df['date'] > tag_in_7)]
    df_updated = pd.concat([df_without_this_week, edited_df_this_week], ignore_index=True)

    # 編集内容が元のデータと異なっているか確認
    # ここでは単純に保存ボタンで更新をトリガー
    if st.button("👍 Ändern"):
        try:
            update_gsheet_and_rerun(df_updated)
            st.success("Änderungen wurden erfolgreich gespeichert und in Google Sheets aktualisiert!")
        except Exception as e:
            st.error(f"Fehler beim Speichern der Änderungen: {e}")

elif mode == 'Speise vor einem Jahr - für 2 M.':
    # 指定した月の１ヶ月分のおかず表示部分
    df = load_df()

    # 12ヶ月前、13ヶ月前のデータを表示するコード
    today = pd.Timestamp('today')
    tag_vor_01 = today - pd.Timedelta(days=396)
    tag_vor_02 = today - pd.Timedelta(days=334)

    df = df[(df['date'] >= tag_vor_01) & (df['date'] <= tag_vor_02)]

    # 12ヶ月前、13ヶ月前のデータを表示するコード（終わり）

    # pandasデータフレームを日付順に並べ替えるコード
    df.sort_values(by='date', ascending=True, inplace=True)
    # 指定した月の１ヶ月分のおかず表示部分 Ende
    st.write('##### 🫕 Was gab’s damals? 2 Monate ab vor einem Jahr!')
    st.dataframe(df[['Datum', 'Speise01', 'Speise02', 'Speise03', 'Speise04', 'Speise05']], hide_index=True)

elif mode == 'Datumssuche nach Speise':
    df = load_df()    
    st.write('##### 🍱 Wann war das? Finde das Datum über die Speise!')
    
    search = st.text_input('Gib eine Speise ein!', key=None)
    if search:
        result = df[(df['Speise01'] == search) |
                    (df['Speise02'] == search) |
                    (df['Speise03'] == search) |
                    (df['Speise04'] == search) |
                    (df['Speise05'] == search)]

        if not result.empty:
            # 検索キーワードを含むセルに色を付ける関数
            def highlight_search(s):
                return['background-color: #fff3b0' if search in str(v) else '' for v in s]

            # スタイルを適用
            styled_df = result[['Datum', 'Speise01', 'Speise02', 'Speise03', 'Speise04', 'Speise05']].style.apply(highlight_search, axis=1)

            # スタイル付きのDataFrameを表示
            st.dataframe(styled_df, hide_index=True)

        else:
            st.warning('Gesuchte Speise wurde nicht gefunden.')
