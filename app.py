import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import io

st.set_page_config(
    page_title="ระบบวิเคราะห์ยอดขายและสั่งซื้อน้ำมันเครื่อง",
    page_icon="🛢️",
    layout="wide"
)

# Shell Theme Accent
st.markdown("""
<style>
    /* Shell Theme Accent */
    :root {
        --shell-red: #DD1D21;
        --shell-yellow: #FBCE07;
        --shell-dark: #1E2129;
    }
    
    /* Main Headers */
    h1 {
        color: #DD1D21 !important;
        font-weight: 800 !important;
    }
    
    /* Metric Cards */
    div[data-testid="stMetric"] {
        background-color: rgba(251, 206, 7, 0.08);
        border-left: 5px solid #FBCE07;
        padding: 12px 16px;
        border-radius: 8px;
    }
    div[data-testid="stMetricLabel"] {
        font-weight: 600;
        color: #E2E8F0;
    }
    div[data-testid="stMetricValue"] {
        color: #FBCE07 !important;
        font-weight: 700;
    }
    
    /* Download & Action Buttons */
    .stDownloadButton > button {
        background-color: #DD1D21 !important;
        color: #FFFFFF !important;
        border: 2px solid #FBCE07 !important;
        font-weight: bold !important;
        border-radius: 8px !important;
        padding: 0.5rem 1.2rem !important;
        transition: all 0.3s ease;
    }
    .stDownloadButton > button:hover {
        background-color: #FBCE07 !important;
        color: #111111 !important;
        border-color: #DD1D21 !important;
    }
    
    /* Sliders track & thumb accent */
    div[data-baseweb="slider"] {
        accent-color: #DD1D21 !important;
    }
    
    /* Sidebar header */
    div[data-testid="stSidebar"] h2, div[data-testid="stSidebar"] h3 {
        color: #FBCE07 !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛢️ ระบบวิเคราะห์ยอดขาย & แนะนำการสั่งซื้อประจำเดือน")
st.markdown("อัปโหลดไฟล์รายงาน 2 ไฟล์จากระบบ เพื่อดูแดชบอร์ดสรุปสินค้าขายดีและรายการแนะนำสั่งซื้ออัตโนมัติ (ปัดเศษเต็มลัง)")

# Sidebar Shell Branding (รูปโลโก้ที่อัปโหลดเอง)
import os
logo_filename = "Shell-Logo.png"  # <-- เปลี่ยนชื่อไฟล์ภาพตรงนี้ได้ตามต้องการ

if os.path.exists(logo_filename):
    col_l, col_m, col_r = st.sidebar.columns([1, 2, 1])
    with col_m:
        st.image(logo_filename, width=360)
    st.sidebar.markdown("<div style='margin-bottom: 60px;'></div>", unsafe_allow_html=True)
st.sidebar.header("📁 อัปโหลดไฟล์ประจำเดือน")
file_stock = st.sidebar.file_uploader("1. อัปโหลดไฟล์สต็อก (จัดการคลังสินค้า.xls)", type=['xls', 'xlsx'])
file_sales = st.sidebar.file_uploader("2. อัปโหลดไฟล์ยอดขาย (รายงานขนาดการขาย.xls)", type=['xls', 'xlsx'])

# Settings
st.sidebar.header("⚙️ ตั้งค่าเกณฑ์สั่งซื้อ")
lead_time_days = st.sidebar.slider("ระยะเวลารอของ (Lead Time: วัน)", min_value=1, max_value=14, value=3)

st.sidebar.subheader("🛡️ สต็อกสำรองกันขาด (Safety Stock)")
st.sidebar.caption("กำหนดจำนวนสต็อกขั้นต่ำแยกตามกลุ่มสินค้าและขนาด")
safety_filter = st.sidebar.slider("🔧 ไส้กรองน้ำมันเครื่อง / ไส้กรองทั่วไป (ลูก)", min_value=0, max_value=20, value=3, step=1)
safety_coolant_1L = st.sidebar.slider("🧪 น้ำยาหล่อเย็น 1 ลิตร (ขวด)", min_value=0, max_value=20, value=10, step=1)
safety_coolant_4L = st.sidebar.slider("🧪 น้ำยาหล่อเย็น 4 ลิตร (แกลลอน)", min_value=0, max_value=16, value=4, step=1)
safety_oil_1L = st.sidebar.slider("🧴 น้ำมันเครื่อง ≤ 1 ลิตร (ขวด)", min_value=0, max_value=36, value=12, step=1)
safety_oil_4L = st.sidebar.slider("🛢️ น้ำมันเครื่อง 4 ลิตร (แกลลอนเบนซิน)", min_value=0, max_value=16, value=4, step=1)
safety_oil_6L = st.sidebar.slider("🚚 น้ำมันเครื่อง 6 ลิตร (แกลลอนดีเซล)", min_value=0, max_value=16, value=4, step=1)
safety_other = st.sidebar.slider("📦 ขนาดอื่นๆ / ถังใหญ่ (18L, 20L)", min_value=0, max_value=5, value=1, step=1)

# Fixed Pack Sizes
pack_coolant_1L = 10  # หล่อเย็น 1 ลิตร ลังละ 10 ขวด
pack_coolant_4L = 4   # น้ำยาหล่อเย็น 4 ลิตร ลังละ 4 แกลลอน (มาตรฐาน)
pack_oil_1L = 12      # น้ำมันเครื่อง 1 ลิตร ลังละ 12 ขวด
pack_oil_4L = 4       # น้ำมันเครื่อง 4 ลิตร ลังละ 4 แกลลอน
pack_oil_6L = 2       # น้ำมันเครื่อง 6 ลิตร ลังละ 2 แกลลอน

if file_stock is not None and file_sales is not None:
    try:
        # 1. Load Stock
        df_stock = pd.read_excel(file_stock)
        
        # 2. Load Sales (skip 2 header rows of Shell report)
        df_sales_raw = pd.read_excel(file_sales, skiprows=2)
        col_prod = df_sales_raw.columns[0]
        col_size = df_sales_raw.columns[1]
        col_total = df_sales_raw.columns[-1]
        
        sales_df = df_sales_raw[[col_prod, col_size, col_total]].copy()
        sales_df.columns = ['Product_Name', 'Size', 'Total_Sold_Liters']
        sales_df = sales_df.dropna(subset=['Product_Name'])
        sales_df['Product_Name'] = sales_df['Product_Name'].astype(str).str.strip()
        
        # Filter out summary/header rows from sales report
        ignore_keywords = ['หมวดผลิตภัณฑ์หลัก', 'รถยนต์ดีเซล', 'รถยนต์เบนซิน', 'รถยนต์ อีโค คาร์', 
                           'รถยนต์ NGV / CNG', 'สรุปจำนวนลิตร', 'รวม 1-15', 'รวม 16-31', 'รวมทั้งสิ้น', 'รายการผลิตภัณฑ์']
        pattern_ignore = '|'.join(ignore_keywords)
        sales_df = sales_df[~sales_df['Product_Name'].str.contains(pattern_ignore, na=False)]
        sales_df['Total_Sold_Liters'] = pd.to_numeric(sales_df['Total_Sold_Liters'], errors='coerce').fillna(0)
        
        # Group sales in case a product appears multiple times
        sales_grouped = sales_df.groupby('Product_Name', as_index=False)['Total_Sold_Liters'].sum()
        
        # 3. Merge by Product Name
        df_merged = pd.merge(
            df_stock,
            sales_grouped,
            left_on=df_stock['ชื่อสินค้า'].astype(str).str.strip(),
            right_on=sales_grouped['Product_Name'].astype(str).str.strip(),
            how='left'
        )
        
        # Clean columns
        df_merged['Total_Sold_Liters'] = df_merged['Total_Sold_Liters'].fillna(0)
        df_merged['ขนาด(ลิตร)'] = pd.to_numeric(df_merged['ขนาด(ลิตร)'], errors='coerce').fillna(1.0)
        df_merged['จำนวนคงเหลือ/หน่วย'] = pd.to_numeric(df_merged['จำนวนคงเหลือ/หน่วย'], errors='coerce').fillna(0)
        
        # Categorize items
        is_filter = df_merged['ชื่อสินค้า'].str.contains('ไส้กรอง|กรอง|PFO', case=False, na=False) | df_merged['หมวดบริการ'].str.contains('กรอง', case=False, na=False)
        is_coolant = df_merged['ชื่อสินค้า'].str.contains('หล่อเย็น|คูลแลนท์|Coolant|ลองไลฟ์', case=False, na=False) | df_merged['หมวดบริการ'].str.contains('หม้อน้ำ|หล่อเย็น', case=False, na=False)
        
        # Sub-category flags
        is_coolant_1L = is_coolant & (df_merged['ขนาด(ลิตร)'] <= 1.0)
        is_coolant_4L = is_coolant & (df_merged['ขนาด(ลิตร)'] > 1.0)
        is_oil_1L = (~is_filter) & (~is_coolant) & (df_merged['ขนาด(ลิตร)'] <= 1.0)
        is_oil_4L = (~is_filter) & (~is_coolant) & (df_merged['ขนาด(ลิตร)'] > 1.0) & (df_merged['ขนาด(ลิตร)'] <= 4.0)
        is_oil_6L = (~is_filter) & (~is_coolant) & (df_merged['ขนาด(ลิตร)'] > 4.0) & (df_merged['ขนาด(ลิตร)'] <= 6.0)
        is_other = (~is_filter) & (~is_coolant) & (df_merged['ขนาด(ลิตร)'] > 6.0)
        
        # Calculate Units Sold
        df_merged['Units_Sold'] = np.where(
            is_filter,
            df_merged['Total_Sold_Liters'],
            np.where(
                df_merged['ขนาด(ลิตร)'] > 0,
                np.round(df_merged['Total_Sold_Liters'] / df_merged['ขนาด(ลิตร)'], 1),
                df_merged['Total_Sold_Liters']
            )
        )
        
        # Assign Category Label for clarity
        cond_category = [is_filter, is_coolant_1L, is_coolant_4L, is_oil_1L, is_oil_4L, is_oil_6L, is_other]
        choice_category = ['ไส้กรอง', 'หล่อเย็น 1L', 'หล่อเย็น 4L', 'น้ำมันเครื่อง ≤1L', 'น้ำมันเครื่อง 4L', 'น้ำมันเครื่อง 6L', 'ถังใหญ่/อื่นๆ']
        df_merged['หมวดหมู่สินค้า'] = np.select(cond_category, choice_category, default='ทั่วไป')
        
        # Assign Safety Stock
        choice_safety = [safety_filter, safety_coolant_1L, safety_coolant_4L, safety_oil_1L, safety_oil_4L, safety_oil_6L, safety_other]
        df_merged['Safety_Stock'] = np.select(cond_category, choice_safety, default=safety_other)
        
        # Assign Pack Size
        choice_pack = [1, pack_coolant_1L, pack_coolant_4L, pack_oil_1L, pack_oil_4L, pack_oil_6L, 1]
        df_merged['Pack_Size'] = np.select(cond_category, choice_pack, default=1)
        
        # Daily demand & ROP
        df_merged['Daily_Units'] = df_merged['Units_Sold'] / 31.0
        
        # ROP calculation
        is_essential = is_filter | is_coolant
        df_merged['ROP'] = np.where(
            is_essential,
            np.maximum(df_merged['Safety_Stock'], np.ceil((df_merged['Daily_Units'] * lead_time_days) + df_merged['Safety_Stock'])),
            np.ceil((df_merged['Daily_Units'] * lead_time_days) + df_merged['Safety_Stock'])
        )
        
        # Max Stock (Target Coverage)
        target_coverage_days = 15.0
        df_merged['Max_Stock'] = np.where(
            is_essential & (df_merged['Units_Sold'] == 0),
            df_merged['Safety_Stock'] * 2,
            np.ceil((df_merged['Daily_Units'] * target_coverage_days) + df_merged['Safety_Stock'])
        )
        
        # Order trigger condition
        cond_trigger = (
            (is_essential & (df_merged['จำนวนคงเหลือ/หน่วย'] <= df_merged['Safety_Stock'])) |
            ((~is_essential) & (df_merged['จำนวนคงเหลือ/หน่วย'] <= df_merged['ROP']) & (df_merged['Units_Sold'] > 0)) |
            ((~is_essential) & (df_merged['จำนวนคงเหลือ/หน่วย'] <= 0) & (df_merged['Units_Sold'] > 0))
        )
        
        raw_order = np.where(
            cond_trigger,
            np.maximum(0, np.ceil(df_merged['Max_Stock'] - df_merged['จำนวนคงเหลือ/หน่วย'])),
            0
        )
        raw_order = np.where(
            (df_merged['จำนวนคงเหลือ/หน่วย'] <= 0) & cond_trigger & (raw_order < df_merged['Safety_Stock']),
            df_merged['Safety_Stock'],
            raw_order
        )
        df_merged['Raw_Order'] = raw_order.astype(int)
        
        # Pack Size Rounding
        df_merged['Suggested_Packs'] = np.ceil(df_merged['Raw_Order'] / df_merged['Pack_Size']).astype(int)
        df_merged['Suggested_Order'] = (df_merged['Suggested_Packs'] * df_merged['Pack_Size']).astype(int)
        
        # Top Seller Identification
        active_sales = df_merged[(df_merged['Units_Sold'] > 0) & (~is_filter)]['Units_Sold']
        sales_threshold = active_sales.quantile(0.80) if len(active_sales) > 0 else 5.0
        df_merged['Is_Top_Seller'] = (df_merged['Units_Sold'] >= sales_threshold) & (~is_filter)
        
        # Status Assignment
        cond_status = [
            (df_merged['จำนวนคงเหลือ/หน่วย'] <= 0) & (df_merged['Is_Top_Seller']),
            (df_merged['จำนวนคงเหลือ/หน่วย'] <= 0) & (df_merged['Units_Sold'] > 0),
            (is_essential) & (df_merged['จำนวนคงเหลือ/หน่วย'] <= 0),
            (df_merged['จำนวนคงเหลือ/หน่วย'] <= df_merged['ROP']) & (df_merged['Is_Top_Seller']),
            (df_merged['จำนวนคงเหลือ/หน่วย'] <= df_merged['ROP']) & (df_merged['Units_Sold'] > 0),
            (is_essential) & (df_merged['จำนวนคงเหลือ/หน่วย'] <= df_merged['Safety_Stock']),
            (~is_essential) & (df_merged['Units_Sold'] == 0) & (df_merged['จำนวนคงเหลือ/หน่วย'] > 0),
            (df_merged['จำนวนคงเหลือ/หน่วย'] > df_merged['ROP'])
        ]
        choice_status = [
            '🔥 ขายดีแต่ของหมด! (วิกฤต)',
            '🔴 สินค้าหมดสต็อก',
            '🔴 ของใช้จำเป็นหมดสต็อก',
            '⚡ สินค้าขายดีต้องรีบสั่ง',
            '🚨 ต้องสั่งซื้อเพิ่ม',
            '⚠️ สต็อกต่ำกว่าเกณฑ์',
            '🐢 ไม่เคลื่อนไหว (Dead Stock)',
            '🟢 สต็อกปกติ'
        ]
        df_merged['Status'] = np.select(cond_status, choice_status, default='🟢 ปกติ')
        
        # Critical Alert Banner
        critical_out = df_merged[df_merged['Status'] == '🔥 ขายดีแต่ของหมด! (วิกฤต)']
        if len(critical_out) > 0:
            st.error(f"🚨 **แจ้งเตือนเร่งด่วน:** มีสินค้าขายดี **{len(critical_out)} รายการ** ที่สต็อกหมดเกลี้ยง (เสียโอกาสการขาย): " + ", ".join(critical_out['ชื่อสินค้า'].tolist()))
            
        # KPI Row
        st.subheader("📊 สรุปภาพรวมประจำเดือน")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        total_liters = df_merged['Total_Sold_Liters'].sum()
        total_units = df_merged['Units_Sold'].sum()
        need_order_count = len(df_merged[df_merged['Suggested_Packs'] > 0])
        dead_stock_count = len(df_merged[df_merged['Status'] == '🐢 ไม่เคลื่อนไหว (Dead Stock)'])
        
        kpi1.metric("ยอดขายรวม (ลิตร)", f"{total_liters:,.2f} ลิตร")
        kpi2.metric("ยอดขายรวม (ขวด/แกลลอน/ลูก)", f"{total_units:,.2f} ชิ้น")
        kpi3.metric("รายการต้องสั่งด่วน", f"{need_order_count} รายการ", delta=-need_order_count if need_order_count > 0 else 0, delta_color="inverse")
        kpi4.metric("สินค้าไม่มีการขาย (Dead Stock)", f"{dead_stock_count} รายการ")
        
        st.divider()
        
        # Chart Row
        col_chart1, col_chart2 = st.columns([6, 4])
        
        with col_chart1:
            st.markdown("### 🏆 10 อันดับสินค้าขายดีที่สุด (ยอดขาย: ลิตร/ชิ้น)")
            top10 = df_merged[df_merged['Units_Sold'] > 0].sort_values(by='Units_Sold', ascending=False).head(10)
            if len(top10) > 0:
                fig_bar = px.bar(
                    top10,
                    x='Units_Sold',
                    y='ชื่อสินค้า',
                    orientation='h',
                    text='Units_Sold',
                    color='Units_Sold',
                    color_continuous_scale='Reds'
                )
                fig_bar.update_traces(texttemplate='%{text:.2f}', textposition='outside')
                fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False, height=450)
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.write("ไม่พบข้อมูลยอดขาย")
            
        with col_chart2:
            st.markdown("### 🎯 สัดส่วนสถานะสต็อกสินค้า")
            status_summary = df_merged['Status'].value_counts().reset_index()
            status_summary.columns = ['Status', 'Count']
            fig_pie = px.pie(
                status_summary,
                values='Count',
                names='Status',
                color='Status',
                color_discrete_map={
                    '🔥 ขายดีแต่ของหมด! (วิกฤต)': '#780000',
                    '🔴 สินค้าหมดสต็อก': '#e63946',
                    '🔴 ของใช้จำเป็นหมดสต็อก': '#ba181b',
                    '⚡ สินค้าขายดีต้องรีบสั่ง': '#d97706',
                    '🚨 ต้องสั่งซื้อเพิ่ม': '#f4a261',
                    '⚠️ สต็อกต่ำกว่าเกณฑ์': '#e09f3e',
                    '🐢 ไม่เคลื่อนไหว (Dead Stock)': '#a8dadc',
                    '🟢 สต็อกปกติ': '#2a9d8f'
                }
            )
            fig_pie.update_layout(height=450)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        st.divider()
        
        # Reorder Action Table
        st.subheader("📋 รายการที่ต้องเปิดบิลสั่งซื้อรอบนี้ (Action Order List - ปัดเต็มลัง)")
        order_list = df_merged[df_merged['Suggested_Packs'] > 0].copy()
        
        if len(order_list) > 0:
            order_list['Sort_Priority'] = np.where(order_list['Status'].str.contains('🔥'), 1, 
                                          np.where(order_list['Status'].str.contains('⚡'), 2, 3))
            order_list = order_list.sort_values(by=['Sort_Priority', 'Suggested_Order'], ascending=[True, False])
            
            order_table = order_list[['รหัสสินค้า', 'ชื่อสินค้า', 'หมวดหมู่สินค้า', 'ขนาด(ลิตร)', 'จำนวนคงเหลือ/หน่วย', 'Units_Sold', 'Safety_Stock', 'Pack_Size', 'Suggested_Packs', 'Suggested_Order', 'Status']].copy()
            order_table.columns = ['รหัสสินค้า', 'ชื่อสินค้า', 'หมวดหมู่', 'ขนาด(ลิตร)', 'สต็อกคงเหลือ', 'ยอดขายเดือนนี้ (ชิ้น)', 'สต็อกสำรอง (Safety)', 'บรรจุต่อลัง', 'สั่งซื้อ (ลัง)', 'สั่งซื้อรวม (ชิ้น/แกลลอน)', 'สถานะ']
            
            def color_status(val):
                s_val = str(val)
                if '🔥' in s_val:
                    return 'background-color: #ffcccc; font-weight: bold; color: #990000;'
                elif '🔴' in s_val:
                    return 'background-color: #ffe6e6; color: #cc0000;'
                elif '⚡' in s_val or '🚨' in s_val or '⚠️' in s_val:
                    return 'background-color: #fff3cd; color: #856404;'
                return ''

            styler = order_table.style
            float_cols = ['ขนาด(ลิตร)', 'ยอดขายเดือนนี้ (ชิ้น)']
            styler = styler.format("{:.2f}", subset=[c for c in float_cols if c in order_table.columns])
            int_cols = ['สต็อกคงเหลือ', 'สต็อกสำรอง (Safety)', 'บรรจุต่อลัง', 'สั่งซื้อ (ลัง)', 'สั่งซื้อรวม (ชิ้น/แกลลอน)']
            styler = styler.format("{:d}", subset=[c for c in int_cols if c in order_table.columns])

            if hasattr(styler, 'map'):
                styled_df = styler.map(color_status, subset=['สถานะ'])
            else:
                styled_df = styler.applymap(color_status, subset=['สถานะ'])
                
            st.dataframe(styled_df, use_container_width=True)
            
            # Excel export
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                order_table.to_excel(writer, index=False, sheet_name='Action_Order_List')
            excel_data = output.getvalue()
            
            st.download_button(
                label="📥 ดาวน์โหลดใบสั่งซื้อ (Excel) เพื่อส่งเซลส์",
                data=excel_data,
                file_name="รายการสั่งซื้อน้ำมันเครื่อง_หล่อเย็น_ไส้กรอง.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.success("🎉 สต็อกมีเพียงพอทุกรายการ ยังไม่มีรายการที่ต้องสั่งซื้อเพิ่มในรอบนี้!")
            
        # Dead Stock Section
        with st.expander("🔍 ดูรายการสินค้าที่ไม่มียอดขายในเดือนนี้ (Dead Stock / Slow-Moving)"):
            dead_df = df_merged[df_merged['Status'] == '🐢 ไม่เคลื่อนไหว (Dead Stock)'][['รหัสสินค้า', 'ชื่อสินค้า', 'หมวดหมู่สินค้า', 'ขนาด(ลิตร)', 'จำนวนคงเหลือ/หน่วย']].sort_values(by='จำนวนคงเหลือ/หน่วย', ascending=False)
            dead_df.columns = ['รหัสสินค้า', 'ชื่อสินค้า', 'หมวดหมู่', 'ขนาด(ลิตร)', 'สต็อกคงเหลือ']
            st.dataframe(dead_df.style.format({'ขนาด(ลิตร)': '{:.2f}', 'สต็อกคงเหลือ': '{:d}'}), use_container_width=True)
            
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการประมวลผลไฟล์: {e}")
else:
    st.info("👈 กรุณาอัปโหลดไฟล์ 'จัดการคลังสินค้า.xls' และ 'รายงานขนาดการขาย.xls' ที่แถบเมนูด้านซ้ายเพื่อเริ่มประมวลผล")
