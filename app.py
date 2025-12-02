# --- UI LAYOUT ---
st.title("🤖 Intelligent Exam Seating Allocator")
st.markdown("Upload student data, define halls, and let AI generate the seating plan without adjacent subject collisions.")

# Sidebar: Hall Configuration
with st.sidebar:
    st.header("1. Configuration")
    upload_hall = st.toggle("Upload Hall List Excel?")
    
    halls_df = pd.DataFrame()
    
    if upload_hall:
        # FIX 1: Add 'xls' to the allowed types here
        h_file = st.file_uploader("Upload Hall Excel (Cols: Hall_Name, Capacity)", type=['xlsx', 'xls'])
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
    # Check for secrets first, otherwise ask user
    if 'OPENAI_API_KEY' in st.secrets:
        api_key = st.secrets['OPENAI_API_KEY']
    else:
        api_key = st.text_input("OpenAI API Key (for Chat)", type="password")

# Main Area: Student Upload
st.header("2. Student Data")
# FIX 2: Add 'xls' to the allowed types here as well
uploaded_files = st.file_uploader("Upload Student Lists (Cols: Student, Course)", type=['xlsx', 'xls'], accept_multiple_files=True)

if uploaded_files:
    dfs = []
    for f in uploaded_files:
        try:
            # Pandas automatically detects .xls vs .xlsx if libraries are installed
            df = pd.read_excel(f)
            parsed = parse_student_data(df)
            if parsed is not None:
                dfs.append(parsed)
            else:
                st.error(f"File {f.name} missing 'Student' or 'Course' columns.")
        except Exception as e:
            st.error(f"Error reading {f.name}: {e}")
            
    if dfs:
        # ... rest of the code remains the same ...
        full_data = pd.concat(dfs, ignore_index=True)
        st.info(f"Loaded {len(full_data)} students.")
        
        if st.button("🚀 Generate Allocation"):
            with st.spinner("Allocating seats..."):
                res_df, visuals = allocate_seats(full_data, halls_df)
                
                st.session_state['allocation'] = res_df
                st.session_state['visuals'] = visuals
                
                st.success("Allocation Done!")
