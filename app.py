import streamlit as st
import pandas as pd
import re
import io
import xlsxwriter

# --- CONFIGURATION ---
st.set_page_config(page_title="AI Exam Seater", layout="wide")

# --- HELPER FUNCTIONS ---

def parse_student_data(df):
    """
    Smartly finds the header row (searching for 'Student') and parses data.
    Handles 'Name(RegNo)' and 'Subject(Code)' formats robustly.
    """
    # 1. HEADER DETECTION
    # Strip whitespace from current columns just in case
    df.columns = df.columns.astype(str).str.strip()
    
    header_found = False
    
    # Check if the current headers are already correct
    if 'Student' in df.columns and ('Course' in df.columns or 'Branch Name' in df.columns):
        header_found = True
    else:
        # If not, scan the first 20 rows to find the word "Student"
        for i, row in df.head(20).iterrows():
            # Convert row to string and strip whitespace
            row_values = [str(x).strip() for x in row.values]
            
            # Check if "Student" is in this row
            if "Student" in row_values:
                # Make this row the new header
                df.columns = row_values
                # Drop data before this row and reset index
                df = df.iloc[i+1:].reset_index(drop=True)
                header_found = True
                break
    
    if not header_found:
        return None

    # 2. COLUMN CLEANING
    # Re-strip columns to handle things like " \tCourse"
    df.columns = df.columns.astype(str).str.strip()
    
    # Map weird column names to our standard ones
    col_map = {}
    for c in df.columns:
        if 'Student' in c: 
            col_map[c] = 'Student'
        elif 'Course' in c: 
            col_map[c] = 'Course'
        elif 'Branch Name' in c: # Fallback
            col_map[c] = 'Course'
            
    df = df.rename(columns=col_map)
    
    # Final check
    if 'Student' not in df.columns or 'Course' not in df.columns:
        return None

    # 3. DATA EXTRACTION (UPDATED REGEX)
    cleaned_data = []
    for index, row in df.iterrows():
        raw_student = str(row.get('Student', ''))
        raw_course = str(row.get('Course', ''))
        
        # SKIP EMPTY ROWS
        if raw_student == 'nan' or raw_student == '':
            continue
            
        # Parse Student: Name(RegNo)
        # Regex: Matches "Name Name (RegNo)"
        student_match = re.search(r"^(.*)\((.*)\)\s*$", raw_student)
        
        if student_match:
            name = student_match.group(1).strip()
            reg_no = student_match.group(2).strip()
        else:
            name = raw_student.strip()
            reg_no = "N/A"

        # Parse Course: Subject Name(Subject Code)
        # Regex Breakdown:
        # ^(.*)        -> Capture everything at start (Subject Name)
        # \(\s* -> Match opening parenthesis and optional spaces
        # ([^)]+)      -> Capture everything inside that is NOT a closing parenthesis (Subject Code)
        # \s*\)        -> Match closing parenthesis and optional spaces
        # \s*$         -> Match any trailing spaces at end of string
        course_match = re.search(r"^(.*)\(\s*([^)]+)\s*\)\s*$", raw_course)
        
        if course_match:
            subject = course_match.group(1).strip()
            code = course_match.group(2).strip()
        else:
            # Fallback: if no parens, use the whole string for both
            subject = raw_course.strip()
            code = raw_course.strip()

        cleaned_data.append({
            'Name': name,
            'Register_No': reg_no,
            'Subject_Name': subject,
            'Subject_Code': code,
        })
            
    return pd.DataFrame(cleaned_data)

def allocate_seats(students_df, halls_df):
    """
    Distributes students into halls preventing adjacent same-subjects.
    """
    # Randomize students
    students_df = students_df.sample(frac=1).reset_index(drop=True)
    
    allocation_results = []
    hall_visuals = {}
    
    total_students = len(students_df)
    
    # Calculate global distribution target
    if len(halls_df) > 0:
        base_fill = total_students // len(halls_df)
    else:
        base_fill = 0
        
    for _, hall in halls_df.iterrows():
        hall_name = hall['Hall_Name']
        capacity = int(hall['Capacity'])
        
        # Dynamic Target: Base fill + buffer, capped at capacity
        target_fill = int(base_fill * 1.2) 
        limit = min(capacity, target_fill) 
        
        hall_layout = []
        previous_subject = None
        filled_count = 0
        
        # Loop to fill this specific hall
        seats_checked = 0
        while filled_count < limit and not students_df.empty:
            seats_checked += 1
            if seats_checked > limit * 3: break 

            candidate_found = False
            
            # Find a valid student
            for idx, student in students_df.iterrows():
                # Constraint: Current subject != Previous subject
                if student['Subject_Code'] != previous_subject:
                    
                    allocation_results.append({
                        'Hall': hall_name,
                        'Seat_No': filled_count + 1,
                        'Name': student['Name'],
                        'Register_No': student['Register_No'],
                        'Subject_Code': student['Subject_Code'],
                        'Subject_Name': student['Subject_Name']
                    })
                    
                    # Add to visual layout list (RegNo + Code)
                    hall_layout.append(f"{student['Register_No']}\n{student['Subject_Code']}")
                    
                    previous_subject = student['Subject_Code']
                    students_df = students_df.drop(idx)
                    candidate_found = True
                    filled_count += 1
                    break
            
            if not candidate_found and not students_df.empty:
                hall_layout.append("EMPTY")
                previous_subject = None 
                filled_count += 1

        hall_visuals[hall_name] = hall_layout

    return pd.DataFrame(allocation_results), hall_visuals

def generate_excel(master_df, hall_visuals):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Sheet 1: Master List
        master_df.to_excel(writer, sheet_name='Master_Allocation', index=False)
        
        # Visual Sheets
        workbook = writer.book
        cell_fmt = workbook.add_format({'text_wrap': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        
        for hall, seats in hall_visuals.items():
            # Excel sheet name limit clean up
            safe_name = str(hall).replace(":", "").replace("/", "")[:30]
            ws = workbook.add_worksheet(safe_name)
            
            cols = 5 # Visual grid width
            row, col = 0, 0
            
            for seat in seats:
                ws.write(row, col, seat, cell_fmt)
                col += 1
                if col >= cols:
                    col = 0
                    row += 1
            ws.set_column(0, cols, 25)
            
    return output.getvalue()

# --- UI LAYOUT ---
st.title("🤖 Intelligent Exam Seating Allocator")

# Sidebar: Hall Configuration
with st.sidebar:
    st.header("1. Hall Setup")
    upload_hall = st.toggle("Upload Hall List Excel?")
    
    halls_df = pd.DataFrame()
    
    if upload_hall:
        h_file = st.file_uploader("Upload Hall Excel", type=['xlsx', 'xls'])
        if h_file:
            try:
                halls_df = pd.read_excel(h_file)
            except:
                halls_df = pd.read_csv(h_file) # Fallback
    else:
        num_halls = st.number_input("Number of Halls", 1, 100, 10)
        seats_per_hall = st.number_input("Seats per Hall", 1, 200, 30)
        halls_df = pd.DataFrame({
            'Hall_Name': [f"Hall {i+1}" for i in range(num_halls)],
            'Capacity': [seats_per_hall] * num_halls
        })
    
    st.write("---")
    if 'OPENAI_API_KEY' in st.secrets:
        api_key = st.secrets['OPENAI_API_KEY']
    else:
        api_key = st.text_input("OpenAI API Key (Optional)", type="password")

# Main Area: Student Upload
st.header("2. Upload Student Data")
uploaded_files = st.file_uploader("Upload Student Lists (Excel/CSV)", type=['xlsx', 'xls', 'csv'], accept_multiple_files=True)

if uploaded_files:
    dfs = []
    for f in uploaded_files:
        try:
            # Robust Reader: Handles CSVs masquerading as XLS
            try:
                if f.name.endswith('.csv'):
                     df = pd.read_csv(f, header=None)
                else:
                     df = pd.read_excel(f, header=None)
            except:
                # Fallback: if excel fail, try csv
                f.seek(0)
                df = pd.read_csv(f, header=None)
            
            parsed = parse_student_data(df)
            
            if parsed is not None and not parsed.empty:
                dfs.append(parsed)
                st.success(f"✅ Loaded {len(parsed)} students from {f.name}")
            else:
                st.warning(f"⚠️ Could not parse data from {f.name}. Check headers.")
                
        except Exception as e:
            st.error(f"❌ Error reading {f.name}: {e}")
            
    if dfs:
        full_data = pd.concat(dfs, ignore_index=True)
        st.info(f"Total Students: {len(full_data)}")
        st.write("### Data Preview (Check Subject Name/Code)")
        st.dataframe(full_data.head()) # Show user the parsed data to verify
        
        if st.button("🚀 Generate Seating Plan"):
            if halls_df.empty:
                st.error("Please configure halls first!")
            else:
                with st.spinner("Allocating seats..."):
                    res_df, visuals = allocate_seats(full_data, halls_df)
                    st.session_state['allocation'] = res_df
                    st.session_state['visuals'] = visuals
                    st.success("Allocation Complete!")

# --- RESULTS ---
if 'allocation' in st.session_state:
    tab1, tab2 = st.tabs(["📊 Download & View", "💬 Chat Assistant"])
    
    with tab1:
        st.dataframe(st.session_state['allocation'].head(10))
        excel_data = generate_excel(st.session_state['allocation'], st.session_state['visuals'])
        st.download_button("📥 Download Final Excel", excel_data, "seating_plan.xlsx")
    
    with tab2:
        if api_key:
            from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo", api_key=api_key)
            agent = create_pandas_dataframe_agent(llm, st.session_state['allocation'], verbose=True, allow_dangerous_code=True)
            prompt = st.text_input("Ask the AI:")
            if prompt:
                st.write(agent.run(prompt))
        else:
            st.warning("Enter API Key in sidebar to use Chat.")
