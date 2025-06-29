import streamlit as st
import sqlite3
import google.generativeai as genai
import os
from dotenv import load_dotenv
import random
import json # New import for JSON parsing

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
DB_NAME = 'burger_king.db'
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    st.error("Gemini API Key not found. Please set GEMINI_API_KEY in your .env file.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = 'gemini-1.5-flash-latest' # Using the model you confirmed works
model = genai.GenerativeModel(MODEL_NAME)

# --- Burger Stack Game Configuration ---
WHOOPER_RECIPE = [
    {"name": "Bottom Bun", "emoji": "🍔⬇️"},
    {"name": "Patty", "emoji": "🥩"},
    {"name": "Cheese", "emoji": "🧀"},
    {"name": "Pickles", "emoji": "🥒"},
    {"name": "Tomato", "emoji": "🍅"},
    {"name": "Lettuce", "emoji": "🥬"},
    {"name": "Ketchup", "emoji": "🥫"},
    {"name": "Mayonnaise", "emoji": "⚪"},
    {"name": "Onion", "emoji": "🧅"},
    {"name": "Top Bun", "emoji": "🍔⬆️"}
]

# --- Database Functions (kept for potential fallback or future use) ---
@st.cache_resource
def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def get_order_details(order_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT OrderID, Items, Status FROM orders WHERE OrderID = ?", (order_id,))
    order_data = cursor.fetchone()
    return order_data

# (Removed get_quiz_questions from DB, as we're primarily using AI now.
# You can re-add if you want a choice between DB and AI quizzes)

# --- AI Integration: Fun Fact Generation Function (from previous step) ---
@st.cache_data(ttl=3600) # Cache facts for 1 hour to reduce API calls
def generate_fun_fact(item_name):
    if not item_name:
        return "Did you know: Enjoying your meal is the most fun fact!"

    fallback_facts = {
        "burger": ["Did you know: The hamburger's origin is debated, but many believe it came from Hamburg, Germany!"],
        "coke": ["Did you know: Coca-Cola was originally invented as a patent medicine!"],
        "whopper": ["Did you know: The Whopper was introduced by Burger King in 1957!"],
        "fries": ["Did you know: French fries might actually originate from Belgium, not France!"],
        "chicken nuggets": ["Did you know: Chicken nuggets were invented in the 1950s by Robert C. Baker at Cornell University!"],
        "general": ["Did you know: Food tastes better when you're having fun!"]
    }

    clean_item = item_name.replace("x", "").strip().split(' ')[-1].lower()
    selected_fallback = random.choice(fallback_facts.get(clean_item, fallback_facts["general"]))

    try:
        prompt = f"Give me one very short, engaging, and fun fact about {clean_item} relevant to fast food. Make it sound like a quick trivia tidbit. Do not include intros like 'Here's a fun fact' or 'Did you know', just the fact itself."
        response = model.generate_content(prompt)

        if response and response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            fact = response.candidates[0].content.parts[0].text
            if "i cannot fulfill this request" in fact.lower() or "not appropriate" in fact.lower():
                return selected_fallback
            return fact
        else:
            st.warning("AI did not return a valid fact. Using a fallback fact.")
            return selected_fallback
    except Exception as e:
        st.error(f"Error generating AI fact: {e}. Using a fallback fact.")
        return selected_fallback


# --- AI Integration: Quiz Generation Function ---
@st.cache_data(ttl=300) # Cache generated quizzes for 5 minutes (adjust as needed)
def generate_quiz_questions_ai(quiz_topic, num_questions=5):
    """
    Generates quiz questions using the Gemini API for a given topic.
    Returns questions in a format suitable for the quiz UI.
    """
    # Fallback questions in case AI generation fails
    fallback_questions = [
        {"QuestionText": "What is the capital of France?", "ShuffledOptions": ["Paris", "London", "Rome", "Berlin"], "NewCorrectOption": "A"},
        {"QuestionText": "Which animal lays eggs?", "ShuffledOptions": ["Dog", "Chicken", "Cow", "Cat"], "NewCorrectOption": "B"},
        {"QuestionText": "What is 2 + 2?", "ShuffledOptions": ["3", "4", "5", "6"], "NewCorrectOption": "B"}
    ]

    # Adjust topic for better prompting if it's a specific item
    effective_topic = quiz_topic.strip()
    if "trivia" not in effective_topic.lower() and "quiz" not in effective_topic.lower():
        effective_topic = f"{effective_topic} Trivia Quiz"
    # effective_topic = quiz_topic.replace("x", "").strip().replace(" ", " French Fries ").capitalize()
    # if "coke" in effective_topic.lower():
    #     effective_topic = "Coca-Cola and soft drinks"
    # elif "burger" in effective_topic.lower() or "whopper" in effective_topic.lower():
    #     effective_topic = "Burger King and burgers"
    # elif "fries" in effective_topic.lower():
    #     effective_topic = "French fries and side dishes"
    # elif "nuggets" in effective_topic.lower():
    #     effective_topic = "Chicken nuggets and fast food chicken"
    # else:
    #     effective_topic = "fast food in general"

    # Craft the prompt to ask for JSON output
    prompt = f"""Generate {num_questions} multiple-choice quiz questions about {effective_topic}.
    Each question should have 4 options (A, B, C, D) and specify the correct option.
    Return the output as a JSON array of objects. Each object should have the following keys:
    "question_text": The question itself.
    "option_a": Text for option A.
    "option_b": Text for option B.
    "option_c": Text for option C.
    "option_d": Text for option D.
    "correct_option": The letter of the correct option (A, B, C, or D).

    Example JSON structure for one question:
    {{
      "question_text": "What is the capital of France?",
      "option_a": "Paris",
      "option_b": "London",
      "option_c": "Rome",
      "option_d": "Berlin",
      "correct_option": "A"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        
        # Ensure the response is valid and contains text
        if response and response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            raw_json_str = response.candidates[0].content.parts[0].text
            
            # # Remove markdown code block if present
            # if raw_json_str.startswith("```json"):
            #     raw_json_str = raw_json_str[7:]
            # if raw_json_str.endswith("```"):
            #     raw_json_str = raw_json_str[:-3]
            # More robust removal of markdown code block fences
            if raw_json_str.startswith("```json"):
                raw_json_str = raw_json_str[len("```json"):].strip()
            if raw_json_str.endswith("```"):
                raw_json_str = raw_json_str[:-len("```")].strip()
            
            quiz_data = json.loads(raw_json_str)

            processed_questions = []
            for q_data in quiz_data:
                options = [q_data['option_a'], q_data['option_b'], q_data['option_c'], q_data['option_d']]
                
                # Check if correct_option is a letter or numerical index
                correct_letter = q_data['correct_option'].upper()
                if correct_letter in ['A', 'B', 'C', 'D']:
                    correct_option_text = q_data[f'option_{correct_letter.lower()}']
                else:
                    # Fallback if AI provides an invalid correct_option letter, pick a random one
                    correct_option_text = options[0] # Default to first option
                    correct_letter = 'A'
                    st.warning(f"AI returned invalid correct_option '{q_data.get('correct_option', 'N/A')}', defaulting to 'A'.")

                random.shuffle(options) # Shuffle options for display

                # Find the new correct letter after shuffling
                new_correct_letter = None
                for i, opt in enumerate(options):
                    if opt == correct_option_text:
                        new_correct_letter = chr(65 + i) # Convert index back to A, B, C, D
                        break
                
                if new_correct_letter is None: # Fallback if correct option text isn't found after shuffling (shouldn't happen)
                    new_correct_letter = 'A' # Default to A
                    st.warning("Correct option not found after shuffling, defaulting to A.")

                processed_questions.append({
                    "QuestionText": q_data['question_text'],
                    "ShuffledOptions": options,
                    "NewCorrectOption": new_correct_letter
                })
            
            if not processed_questions:
                st.warning("AI generated empty quiz data. Using fallback questions.")
                return fallback_questions
            
            return processed_questions

        else:
            st.warning("AI did not return a valid quiz. Using fallback questions.")
            return fallback_questions

    except json.JSONDecodeError as e:
        st.error(f"Error parsing AI quiz response (JSON invalid): {e}. Raw response: {response.candidates[0].content.parts[0].text if response.candidates else 'N/A'}. Using fallback questions.")
        return fallback_questions
    except Exception as e:
        st.error(f"Error generating AI quiz: {e}. Using fallback questions.")
        return fallback_questions


# --- Quiz State Management ---
def initialize_quiz_state():
    """Initializes or resets only the quiz state in st.session_state."""
    st.session_state.quiz_active = False
    st.session_state.current_question_index = 0
    st.session_state.score = 0
    st.session_state.questions = []
    st.session_state.quiz_topic = None
    st.session_state.quiz_completed = False

    # Clear all dynamically generated question-specific state variables
    keys_to_delete = [
        key for key in st.session_state.keys()
        if key.startswith("quiz_q_") and (
            key.endswith("_submitted") or
            key.endswith("_selected_option") or
            key.endswith("_radio") or
            key.endswith("_feedback_msg") or
            key.endswith("_feedback_type")
        )
    ]
    for key in keys_to_delete:
        del st.session_state[key]

# --- Game State Management ---
def initialize_game_state():
    """Initializes or resets only the 'Guess the Number' game state."""
    st.session_state.guess_number_active = False # Renamed to be specific
    st.session_state.secret_number = None
    st.session_state.attempts = 0
    st.session_state.game_message = ""
    st.session_state.game_over = False
    st.session_state.game_input_key = 0 # To force reset of number input widget

def initialize_burger_stack_game_state():
    """Initializes or resets only the 'Burger Stack' game state."""
    st.session_state.burger_stack_active = False
    st.session_state.current_stack = []
    st.session_state.next_ingredient_index = 0
    st.session_state.burger_game_status = "playing" # "playing", "win", "lose"
    st.session_state.burger_game_feedback = "Click the ingredients in order to build a Whopper!"

# --- Master State Reset Function ---
def reset_all_states():
    """Resets all feature-specific states to return to main order details view."""
    initialize_quiz_state()
    initialize_game_state() # Resets Guess the Number
    initialize_burger_stack_game_state() # Resets Burger Stack
    st.session_state.mini_game_menu_active = False # New state for game selection menu

# Ensure session state is initialized for all features
if 'quiz_active' not in st.session_state:
    reset_all_states() # Initialize all states on first run
    st.session_state.guess_number_active = False # Explicitly ensure this is off initially
    st.session_state.burger_stack_active = False # Explicitly ensure this is off initially



# --- Streamlit Application UI ---

st.set_page_config(
    page_title="Burger King Engage & Entertain",
    page_icon="🍔",
    layout="centered"
)

st.title("🍔 Burger King - Engage & Entertain 🎮")
st.markdown("---")

# Main content area - only show order details if no quiz or game is active
if not st.session_state.quiz_active and not st.session_state.quiz_completed and \
   not st.session_state.guess_number_active and not st.session_state.burger_stack_active and \
   not st.session_state.mini_game_menu_active: # Added mini_game_menu_active here
    # --- Order ID Input and Details Display ---
    st.header("Your Order Experience")
    st.write("Scan the QR code on your menu and enter your Order ID below to start the fun!")

    order_id_input = st.text_input(
        "Enter your Order ID:",
        max_chars=10,
        placeholder="e.g., 38",
        help="Type the order ID found on your receipt or given by the cashier."
    )

    if order_id_input:
        order_details = get_order_details(order_id_input)

        if order_details:
            st.subheader(f"Details for Order ID: `{order_id_input}`")
            items = order_details['Items']
            status = order_details['Status']

            st.success("Order Found! 🎉")
            st.write(f"**Items:** {items}")
            st.write(f"**Status:** {status}")

            st.markdown("---")

            # --- Options Menu ---
            st.subheader("What would you like to do while you wait?")

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("💡 Fun Facts about your order"):
                    with st.spinner("Generating fun fact..."):
                        first_item = items.split(',')[0].strip()
                        fun_fact = generate_fun_fact(first_item)
                        st.info(fun_fact)

            with col2:
                if st.button("🧠 Play a Quiz related to your order"):
                    reset_all_states() # Ensure all other features are reset
                    quiz_topic_to_generate = "Fast Food" # Default topic

                    normalized_items = items.lower()

                    if "whopper" in normalized_items:
                        quiz_topic_to_generate = "Burger King Whopper"
                    elif "chicken nuggets" in normalized_items:
                        quiz_topic_to_generate = "Chicken Nuggets"
                    elif "fries" in normalized_items:
                        quiz_topic_to_generate = "French Fries"
                    elif "coke" in normalized_items or "soda" in normalized_items:
                        quiz_topic_to_generate = "Coca-Cola"
                    elif "veggie burger" in normalized_items:
                        quiz_topic_to_generate = "Veggie Burgers"
                    elif "burger" in normalized_items:
                        quiz_topic_to_generate = "Burger King Burgers"
                    elif "water" in normalized_items:
                        quiz_topic_to_generate = "Drinks and Beverages"

                    print(f"--- Debugging Quiz Topic ---")
                    print(f"Order Items: '{items}'")
                    print(f"Determined Quiz Topic: '{quiz_topic_to_generate}'")
                    print(f"----------------------------")

                    with st.spinner(f"Generating quiz about {quiz_topic_to_generate.lower()}..."):
                        ai_quiz_questions = generate_quiz_questions_ai(quiz_topic_to_generate, num_questions=5)

                    if ai_quiz_questions:
                        st.session_state.quiz_active = True
                        st.session_state.questions = ai_quiz_questions
                        st.session_state.quiz_topic = quiz_topic_to_generate
                        st.session_state.current_question_index = 0
                        st.session_state.score = 0
                        st.session_state.quiz_completed = False # Ensure this is false on new quiz start
                        st.rerun()
                    else:
                        st.warning(f"Could not generate a quiz about {quiz_topic_to_generate}. Please try again later or with a different order.")

            with col3:
                if st.button("🎮 Play a Short Game"):
                    reset_all_states() # Reset all other active features
                    st.session_state.mini_game_menu_active = True # Activate game selection menu
                    st.rerun()

        else:
            st.warning(f"Order ID `{order_id_input}` not found. Please double-check and try again.")
            st.info("Currently, our system recognizes Order IDs: 38, 39, 40, and 41.")

elif st.session_state.mini_game_menu_active:
    st.header("🎮 Choose Your Mini-Game!")
    st.write("Which game would you like to play?")

    col_game_choice1, col_game_choice2 = st.columns(2)

    with col_game_choice1:
        if st.button("🔢 Guess the Number", use_container_width=True):
            reset_all_states() # Reset all states, including menu state
            st.session_state.guess_number_active = True
            st.session_state.secret_number = random.randint(1, 100) # Number between 1 and 100
            st.session_state.game_message = "I'm thinking of a number between 1 and 100. Can you guess it?"
            st.session_state.attempts = 0
            st.rerun()
    with col_game_choice2:
        if st.button("🍔 Build the Whopper", use_container_width=True):
            reset_all_states() # Reset all states, including menu state
            st.session_state.burger_stack_active = True
            st.session_state.current_stack = []
            st.session_state.next_ingredient_index = 0
            st.session_state.burger_game_status = "playing"
            st.session_state.burger_game_feedback = "Start by adding the Bottom Bun!"
            st.rerun()

    if st.button("🏠 Return to Order Details", key="game_menu_return"):
        reset_all_states()
        st.rerun()

# --- Quiz Display Logic (This block remains the same as your last working version) ---
elif st.session_state.quiz_active:
    st.header(f"🧠 Quiz Time: {st.session_state.quiz_topic} Trivia Quiz!")
    st.write(f"Question {st.session_state.current_question_index + 1} of {len(st.session_state.questions)}")

    current_question = st.session_state.questions[st.session_state.current_question_index]

    st.subheader(current_question['QuestionText'])

    selected_option_key = f"quiz_q_{st.session_state.current_question_index}_selected_option"
    if selected_option_key not in st.session_state:
        st.session_state[selected_option_key] = None

    selected_option_text = st.radio(
        "Choose your answer:",
        current_question['ShuffledOptions'],
        key=f"quiz_q_{st.session_state.current_question_index}_radio",
        index=current_question['ShuffledOptions'].index(st.session_state[selected_option_key]) if st.session_state[selected_option_key] in current_question['ShuffledOptions'] else None
    )

    if selected_option_text:
        st.session_state[selected_option_key] = selected_option_text

    col_nav1, col_submit, col_nav2 = st.columns([1, 2, 1])

    with col_nav1:
        if st.session_state.current_question_index > 0:
            if st.button("⬅️ Back"):
                st.session_state.current_question_index -= 1
                st.rerun()

    with col_submit:
        submitted_key = f"quiz_q_{st.session_state.current_question_index}_submitted"
        feedback_message_key = f"quiz_q_{st.session_state.current_question_index}_feedback_msg"
        feedback_type_key = f"quiz_q_{st.session_state.current_question_index}_feedback_type"

        if submitted_key not in st.session_state:
            st.session_state[submitted_key] = False
            st.session_state[feedback_message_key] = None
            st.session_state[feedback_type_key] = None

        if not st.session_state[submitted_key] and selected_option_text:
            if st.button("Submit Answer", type="primary", use_container_width=True):
                correct_option_text = current_question['ShuffledOptions'][ord(current_question['NewCorrectOption']) - ord('A')]

                if selected_option_text == correct_option_text:
                    st.session_state.score += 1
                    st.session_state[feedback_message_key] = "Correct! 🎉"
                    st.session_state[feedback_type_key] = 'success'
                else:
                    st.session_state[feedback_message_key] = f"Incorrect. The correct answer was: {correct_option_text}"
                    st.session_state[feedback_type_key] = 'error'

                st.session_state[submitted_key] = True
                st.rerun()
        elif st.session_state[submitted_key]:
            if st.session_state[feedback_type_key] == 'success':
                st.success(st.session_state[feedback_message_key])
            elif st.session_state[feedback_type_key] == 'error':
                st.error(st.session_state[feedback_message_key])

            st.info("You've already answered this question!")

            if st.session_state.current_question_index < len(st.session_state.questions) - 1:
                if st.button("Next Question ▶️", on_click=lambda: st.session_state.update(current_question_index=st.session_state.current_question_index + 1), use_container_width=True):
                    st.rerun()
            else:
                if st.button("Finish Quiz ✅", on_click=lambda: st.session_state.update(quiz_active=False, quiz_completed=True), use_container_width=True):
                    st.rerun()

    with col_nav2:
        if st.button("🏠 Return to Order Details"):
            reset_all_states() # Use the master reset
            st.rerun()

# --- Quiz Completed Logic (This block remains the same) ---
elif st.session_state.quiz_completed:
    st.header("Quiz Completed! 🥳")
    st.subheader(f"You scored: {st.session_state.score} out of {len(st.session_state.questions)}!")

    if st.session_state.score == len(st.session_state.questions):
        st.balloons()
        st.write("Amazing! You're a true trivia master! 🏆")
    elif st.session_state.score >= len(st.session_state.questions) / 2:
        st.write("Good job! You know your stuff. Keep playing! 👍")
    else:
        st.write("Nice try! Keep learning and play again to improve! 😉")

    if st.button("Play Again"):
        reset_all_states() # Use master reset
        st.rerun()
    if st.button("Back to Order Details"):
        reset_all_states() # Use master reset
        st.rerun()

# --- Guess the Number Game Logic (This block remains the same as previous update) ---
elif st.session_state.guess_number_active: # Renamed from game_active to be specific
    st.header("🎮 Guess the Number!")
    st.write("Try to guess the number I'm thinking of, between 1 and 100.")
    st.info(st.session_state.game_message)

    if not st.session_state.game_over:
        user_guess = st.number_input(
            "Enter your guess:",
            min_value=1,
            max_value=100,
            step=1,
            key=f"guess_input_{st.session_state.game_input_key}"
        )

        if st.button("Submit Guess", type="primary"):
            st.session_state.attempts += 1
            if user_guess < st.session_state.secret_number:
                st.session_state.game_message = f"Your guess ({int(user_guess)}) is Too LOW! Try again."
            elif user_guess > st.session_state.secret_number:
                st.session_state.game_message = f"Your guess ({int(user_guess)}) is Too HIGH! Try again."
            else:
                st.session_state.game_message = f"Congratulations! You guessed the number ({int(user_guess)}) in {st.session_state.attempts} attempts! 🎉"
                st.session_state.game_over = True
                st.balloons()
            st.rerun()
    else: # Game is over
        st.write(f"The number was {st.session_state.secret_number}. You took {st.session_state.attempts} attempts.")
        col_game_end1, col_game_end2 = st.columns(2)
        with col_game_end1:
            if st.button("Play Again 🔄"):
                initialize_game_state() # Reset only Guess the Number state
                st.session_state.secret_number = random.randint(1, 100)
                st.session_state.guess_number_active = True # Activate this specific game
                st.session_state.game_input_key += 1
                st.session_state.game_message = "I'm thinking of a number between 1 and 100. Can you guess it?"
                st.rerun()
        with col_game_end2:
            if st.button("🏠 Return to Order Details"):
                reset_all_states() # Master reset
                st.rerun()

    # Always show return to order details button during game (even if not over)
    if not st.session_state.game_over: # Only show if game is still active
        if st.button("🏠 Return to Order Details", key="guess_return_button_active"):
            reset_all_states()
            st.rerun()

# --- Burger Stack Game Logic (NEW BLOCK) ---
elif st.session_state.burger_stack_active:
    st.header("🍔 Build the Whopper!")
    st.write("Click the ingredients in the correct order to build a classic Burger King Whopper.")

    # Display current stack
    if st.session_state.current_stack:
        st.markdown("### Your Whopper Stack:")
        for item in reversed(st.session_state.current_stack): # Display from bottom up
            st.write(f"&nbsp;&nbsp;&nbsp;{item['emoji']} {item['name']}")
        st.markdown("---") # Separator below the stack
    else:
        st.info("Start with the Bottom Bun!")

    st.markdown(st.session_state.burger_game_feedback) # Display feedback

    if st.session_state.burger_game_status == "playing":
        st.subheader("Available Ingredients:")
        cols = st.columns(len(WHOOPER_RECIPE)) # Create columns for each ingredient button

        for i, ingredient in enumerate(WHOOPER_RECIPE):
            with cols[i % len(cols)]: # Use modulo to cycle through columns if recipe is longer than cols
                if st.button(f"{ingredient['emoji']} {ingredient['name']}", key=f"ingredient_btn_{ingredient['name']}"):
                    expected_ingredient = WHOOPER_RECIPE[st.session_state.next_ingredient_index]

                    if ingredient['name'] == expected_ingredient['name']:
                        st.session_state.current_stack.append(ingredient)
                        st.session_state.next_ingredient_index += 1
                        st.session_state.burger_game_feedback = f"Added {ingredient['name']}! Good."

                        if st.session_state.next_ingredient_index == len(WHOOPER_RECIPE):
                            st.session_state.burger_game_status = "win"
                            st.session_state.burger_game_feedback = "Congratulations! You built a perfect Whopper! 🎉"
                            st.balloons()
                    else:
                        st.session_state.burger_game_status = "lose"
                        st.session_state.burger_game_feedback = f"Oops! You added {ingredient['name']}, but the next ingredient should have been {expected_ingredient['name']}. Game Over! 😭"

                    st.rerun() # Rerun to update stack and feedback
    
    # Game Over / Win screen
    if st.session_state.burger_game_status != "playing":
        st.subheader("Game Over!")
        if st.session_state.burger_game_status == "win":
            st.success("You built a perfect Whopper!")
        else: # Lose
            st.error("You made a mistake! Try again.")

        col_burger_end1, col_burger_end2 = st.columns(2)
        with col_burger_end1:
            if st.button("Play Again 🔄", key="burger_play_again"):
                initialize_burger_stack_game_state() # Reset only burger stack game
                st.session_state.burger_stack_active = True # Re-activate
                st.rerun()
        with col_burger_end2:
            if st.button("🏠 Return to Order Details", key="burger_return_from_end"):
                reset_all_states()
                st.rerun()
    
    # Return to order details button always present during game
    if st.session_state.burger_game_status == "playing":
        if st.button("🏠 Return to Order Details", key="burger_return_button_active"):
            reset_all_states()
            st.rerun()


st.markdown("---")
st.caption("Developed by abhishek for Burger King customers. Enjoy your wait! 😊")