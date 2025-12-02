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
    Parses columns 'Student' -> Name, RegNo and 'Course' -> Subject, Code
    Expected formats: "Name(RegNo)" and "Subject(Code)"
    """
    cleaned_data = []
    
    # Check if required columns exist
    if 'Student' not in df.columns or 'Course' not in df.columns:
        return None

    for index, row in df.iterrows():
        raw_student = str(row.get('Student', ''))
        raw_course = str(row.get('Course', ''))
        
        # Regex to extract text inside and outside parentheses
        student_match = re.search(r"(.*)\((.*)\)", raw_student)
        course_match = re.search(r"(.*)\((.*)\)", raw_course)
        
        if student_match and course_match:
            cleaned_data.append({
                'Name': student_match.group(1).strip(),
                'Register_No': student_match.group(2).strip(),
                'Subject_Name': course_match.group(1).strip(),
                'Subject_Code': course_match.group(2).strip(),
            })
        else:
            # Fallback for clean data (if regex fails, take raw value)
            cleaned_data.append({
                'Name': raw_student,
                'Register_No': "N/A", 
                'Subject_Name': raw_course,
                'Subject_Code': raw_course # Treat whole string as code if no parens
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
    
    # Global pointer isn't needed if we drop rows, but helpful for tracking
    
    for _, hall in halls_df.iterrows():
        hall_name = hall['Hall_Name']
        capacity = int(hall['Capacity'])
        
        # Calculate Target Fill for this hall to ensure even distribution across all halls
        # (Total Students / Remaining Halls) - simplified logic here:
        target_fill = int((total_students / len(halls_df)) * 1.1) 
        limit = min(capacity, target_fill) 
        
        hall_layout = []
        previous_subject = None
        filled_count = 0
        
        # Loop to fill the specific hall
        seats_checked = 0
        while filled_count < limit and not students_df.empty:
            seats_checked += 1
            if seats_checked > limit * 2: break # Safety break to prevent infinite loops

            candidate_found = False
            
            # Find a valid student
            for idx, student in students_df.iterrows():
                # Constraint: Current student subject != Previous student subject
                if student['Subject_Code'] != previous_subject:
                    
                    allocation_results.append({
                        'Hall': hall_name,
                        'Seat_No': filled_count + 1,
                        'Name': student['Name'],
                        'Register_No': student['Register_No'],
                        'Subject_Code': student['Subject_Code']
                    })
                    
                    # Add to visual layout list
                    hall_layout.append(f"{student['Register_No']}\n{student['Subject_Code']}")
                    
                    previous_subject = student['Subject_Code']
                    students_df = students_df.drop(idx) # Remove allocated student
                    candidate_found = True
                    filled_count += 1
                    break
            
            if not candidate_found and not students_df.empty:
                # Force Empty Seat if constraint cannot be met
                hall_layout.append("EMPTY")
                previous_subject = None # Reset constraint after empty seat
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
            ws = workbook.add_worksheet(str(hall)[:30]) # Excel sheet name limit
            cols = 5 # Visual grid width
            row, col = 0, 0
            
            for seat in seats:
                ws.write(row, col, seat, cell_fmt)
                col += 1
                if col >= cols:
                    col = 0
                    row += 1
            ws.set_column(0, cols, 20)
            
    return output.getvalue()

# --- UI LAYOUT ---
st.title("🤖 Intelligent Exam Seating Allocator")
st.markdown("Upload student data, define halls, and let AI generate the seating plan without adjacent subject collisions.")

# Sidebar: Hall Configuration
with st.sidebar:
    st.header("1. Configuration")
    upload_hall = st.toggle("Upload Hall List Excel?")
    
    halls_df = pd.DataFrame()
    
    if upload_hall:
        h_file = st.file_uploader("Upload Hall Excel (Cols: Hall_Name, Capacity)", type=['xlsx'])
        if h_file:
            halls_df = pd.read_excel(h_file)
    else:
        num_halls = st.number_input("Number of Halls", 1, 100, 5)
        seats_per_hall = st.number_input("Seats per Hall", 1, 200, 30)
        halls_df = pd.DataFrame({
            'Hall_Name': [f"Hall {i+1}" for i in range(num_halls)],
            'Capacity': [seats_per_hall] * num_halls
        })
    
    st.write("---")
    st.write("### AI Chat (Optional)")
    api_key = st.text_input("OpenAI API Key (for Chat)", type="password")

# Main Area: Student Upload
st.header("2. Student Data")
uploaded_files = st.file_uploader("Upload Student Lists (Cols: Student, Course)", type=['xlsx'], accept_multiple_files=True)

if uploaded_files:
    dfs = []
    for f in uploaded_files:
        df = pd.read_excel(f)
        parsed = parse_student_data(df)
        if parsed is not None:
            dfs.append(parsed)
        else:
            st.error(f"File {f.name} missing 'Student' or 'Course' columns.")
            
    if dfs:
        full_data = pd.concat(dfs, ignore_index=True)
        st.info(f"Loaded {len(full_data)} students.")
        
        if st.button("🚀 Generate Allocation"):
            with st.spinner("Allocating seats..."):
                res_df, visuals = allocate_seats(full_data, halls_df)
                
                # Store in session state for chat interaction
                st.session_state['allocation'] = res_df
                st.session_state['visuals'] = visuals
                
                st.success("Allocation Done!")

# Results Section
if 'allocation' in st.session_state:
    tab1, tab2 = st.tabs(["📊 Visualization & Download", "💬 AI Chat Assistant"])
    
    with tab1:
        st.dataframe(st.session_state['allocation'])
        
        excel_data = generate_excel(st.session_state['allocation'], st.session_state['visuals'])
        st.download_button("📥 Download Allocation Excel", excel_data, "seating_plan.xlsx")
    
    with tab2:
        st.info("Chat with your data (e.g., 'How many students in Hall 1?', 'Remove Hall 5'). Requires API Key.")
        if api_key:
            from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
            from langchain_openai import ChatOpenAI
            
            llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo", api_key=api_key)
            agent = create_pandas_dataframe_agent(llm, st.session_state['allocation'], verbose=True, allow_dangerous_code=True)
            
            prompt = st.text_input("Ask the AI:")
            if prompt:
                with st.spinner("Thinking..."):
                    try:
                        response = agent.run(prompt)
                        st.write(response)
                    except Exception as e:
                        st.error(f"Error: {e}")
