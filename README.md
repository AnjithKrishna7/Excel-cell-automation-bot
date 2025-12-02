# AI Exam Seating Allocator

A Python-based web application that automates exam seating arrangements. It takes unclean Excel data (Name/Register No), distributes students across halls, ensures no two adjacent students have the same subject, and generates visual Excel grids.

## Features
- **Smart Parsing**: Extracts `Name` and `RegNo` from formats like `John Doe(12345)`.
- **Constraint Satisfaction**: Ensures adjacent seats do not share the same subject code.
- **Visual Output**: Generates an Excel file with a grid layout for every exam hall.
- **AI Chat**: (Optional) Chat with the data using OpenAI to query or filter results.

## How to Run

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
