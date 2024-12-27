import streamlit as st
from streamlit_folium import st_folium
from streamlit_option_menu import option_menu
import folium
from folium import plugins
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import json
import requests
from urllib.parse import quote
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up the OpenAI API
from openai import OpenAI
client = OpenAI(api_key = "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")

# Set up the Google Maps API
google_maps_api_key = "AIzaSyDjJ6AesaGlBCDMzdH4wUO0LvRXZK-V2co"

# Custom CSS to improve the UI
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        background-color: #FF4B4B;
        color: white;
        padding: 0.5rem 1rem;
    }
    .main .block-container {
        padding-top: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

def get_coordinates(address, api_key=google_maps_api_key):
    """Get coordinates from an address using either Nominatim or Google Maps API"""
    # First try with Nominatim (free service)
    geolocator = Nominatim(user_agent="my_app")
    location = geolocator.geocode(address)
    
    if location is not None:
        return location.latitude, location.longitude
    
    # Fallback to Google Maps API
    url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={address}&inputtype=textquery&fields=geometry,name&key={api_key}"
    response = requests.get(url)
    data = response.json()
    
    if 'candidates' in data and data['candidates']:
        place = data['candidates'][0]
        return place['geometry']['location']['lat'], place['geometry']['location']['lng']
    
    return None

def calculate_shortest_path(start_coords, destinations):
    """Calculate the optimal path between destinations"""
    path = [start_coords]
    unvisited = destinations.copy()
    
    while unvisited:
        nearest_dest = min(unvisited, key=lambda x: geodesic(path[-1], x).km)
        path.append(nearest_dest)
        unvisited.remove(nearest_dest)
    
    path.append(start_coords)  # Return to start
    return path

def get_place_info(api_key, place_name):
    """Fetch place information from Google Places API"""
    url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={place_name}&inputtype=textquery&fields=geometry,name&key={api_key}"
    response = requests.get(url)
    data = response.json()
    
    if 'candidates' in data and data['candidates']:
        place = data['candidates'][0]
        return {
            'name': place['name'],
            'lat': place['geometry']['location']['lat'],
            'lng': place['geometry']['location']['lng']
        }
    return None

def fetch_place_images(place_name, api_key=google_maps_api_key):
    """Fetch satellite images for a place using Google Static Maps API"""
    place_info = get_place_info(api_key, place_name)
    if place_info:
        lat, lng = place_info['lat'], place_info['lng']
        return f"https://maps.googleapis.com/maps/api/staticmap?center={lat},{lng}&zoom=17&size=400x400&maptype=satellite&key={api_key}"
    return None

def plan_trip():
    """Main function for trip planning"""
    st.title("Plan Your Perfect Trip")
    
    # Create three columns for input fields
    col1, col2, col3 = st.columns([2, 1, 2])
    
    with col1:
        location = st.text_input("🌍 Destination", placeholder="e.g., New York City, USA")
    
    with col2:
        num_days = st.number_input("📅 Number of Days", min_value=1, max_value=14, value=3)
    
    with col3:
        hotel_address = st.text_input("🏨 Hotel Address", placeholder="e.g., 350 W 39th St, New York")

    # Add a submit button with loading state
    if st.button("Generate Travel Plan 🚀", use_container_width=True):
        if not all([location, hotel_address]):
            st.error("Please fill in all required fields!")
            return
            
        with st.spinner("Planning your perfect trip... 🌟"):
            # Get hotel coordinates
            hotel_coords = get_coordinates(hotel_address)
            if not hotel_coords:
                st.error("❌ Could not find the hotel location. Please check the address.")
                return
            
            # Generate travel plan using OpenAI
            prompt = f"""Plan a {num_days}-day trip to {location}, starting from {hotel_address}.
            Generate a JSON object with 'Must-Visit' places day-wise, including short descriptions.
            Format: {{'Day 1': [{{'name': '', 'description': ''}}], ...}}
            Include 3 places per day, considering travel time and location proximity."""
            
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "system", "content": prompt}],
                    temperature=1,
                    max_tokens=1024
                )
                
                result = json.loads(response.choices[0].message.content)
                
                # Process and display the itinerary
                display_itinerary(result, location, hotel_coords, hotel_address)
                
            except Exception as e:
                st.error(f"An error occurred while generating the travel plan: {str(e)}")

def display_itinerary(result, location, hotel_coords, hotel_address):
    """Display the generated itinerary with maps and images"""
    st.success("🎉 Your travel plan is ready!")
    
    day_places = []
    day_coords = []
    
    # Process places and get coordinates
    for day, places in result.items():
        places_coords = []
        processed_places = []
        
        for place in places:
            coords = get_coordinates(f"{place['name']}, {location}")
            if coords:
                place['coords'] = coords
                place['image_url'] = fetch_place_images(f"{place['name']}, {location}")
                places_coords.append(coords)
                processed_places.append(place)
            
        day_places.append(processed_places)
        day_coords.append(places_coords)
    
    # Display itinerary with collapsible sections
    st.subheader("📍 Daily Itinerary")
    
    for day_num, (places, coords) in enumerate(zip(day_places, day_coords), 1):
        with st.expander(f"Day {day_num}", expanded=True):
            cols = st.columns(len(places))
            
            for i, place in enumerate(places):
                with cols[i]:
                    if place['image_url']:
                        st.image(place['image_url'], width=200, caption=place['name'])
                    else:
                        st.info(f"No image available for {place['name']}")
                    st.write(place['description'])
            
            # # Show map button
            # if st.button(f"📍 View Day {day_num} Map", key=f"map_btn_{day_num}"):
            #     path = calculate_shortest_path(hotel_coords, coords)
            #     m = create_map(path, places)
            #     st_folium(m, width=725, key=f"map_{day_num}")
    
    # Display Google Maps links
    st.subheader("🗺️ Navigation Links")
    for day_num, places in enumerate(day_places, 1):
        url = create_google_maps_url(hotel_address, places, location)
        st.markdown(f"[Day {day_num} - Google Maps Navigation]({url}) 🚗")

def create_map(path, places):
    """Create a Folium map with markers and route"""
    m = folium.Map(location=path[0], zoom_start=12)
    
    # Add markers and route
    for i, coords in enumerate(path):
        if i == 0 or i == len(path) - 1:
            folium.Marker(
                coords,
                popup="Hotel",
                icon=folium.Icon(color='red', icon='home')
            ).add_to(m)
        else:
            folium.Marker(
                coords,
                popup=places[i-1]['name'],
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(m)
        
        if i > 0:
            folium.PolyLine(
                [path[i-1], coords],
                color="blue",
                weight=2.5,
                opacity=1
            ).add_to(m)
    
    return m

def create_google_maps_url(hotel_address, places, location):
    """Create Google Maps navigation URL"""
    url = f"https://www.google.com/maps/dir/{quote(hotel_address)}/"
    for place in places:
        url += f"{quote(place['name'])},{quote(location)}/"
    return url + quote(hotel_address)

def local_insights():
    """Standalone interface for getting local travel insights"""
    st.title("Local Travel Insights 🌏")
    
    st.markdown("""
    Get insider knowledge about any destination! Enter a location below to discover local customs, 
    transportation tips, safety advice, food recommendations, and hidden gems that most tourists miss.
    """)
    
    # Create a container for the search interface
    search_container = st.container()
    with search_container:
        col1, col2 = st.columns([3, 1])
        with col1:
            location = st.text_input(
                "Enter your destination:",
                placeholder="e.g., Dubai, UAE",
                key="location_input"
            )
        with col2:
            search_button = st.button("Explore 🔍", use_container_width=True)

    # Process the search when button is clicked
    if search_button and location:
        with st.spinner(f"Gathering local insights about {location}..."):
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": """You are a knowledgeable local expert who has lived in 
                        the specified location for many years. Provide detailed, authentic insights using natural,
                        flowing sentences. Focus on practical, current, and specific information."""},
                        {"role": "user", "content": f"""As a long-time resident of {location}, please provide detailed 
                        insights in natural, flowing sentences about:

                        1. Local customs and etiquette - Share the essential greeting customs, dress codes, and important
                           cultural practices visitors should respect.
                        
                        2. Transportation tips - Explain the best ways to get around, including public transport options,
                           recommended apps, and any travel cards that visitors should get.
                        
                        3. Essential local phrases - Share some common phrases with their meanings and basic pronunciation
                           that visitors would find useful.
                        
                        4. Safety advice - Describe specific areas or situations to be aware of and practical safety tips.
                        
                        5. Best times to visit - Provide specific timing tips for major attractions to avoid crowds and
                           get the best experience.
                        
                        6. Local food guide - Recommend specific restaurants and dishes that offer authentic local cuisine.
                        
                        7. Hidden gems - Share specific locations that tourists often miss and explain what makes them special.
                        
                        Format the response as natural paragraphs, not as a JSON object. Each category should be a
                        complete, flowing description that reads naturally."""}
                    ],
                    temperature=0.7
                )
                
                # Get the text response
                insights = response.choices[0].message.content
                
                # Split insights into sections (assuming they're separated by numbered points)
                sections = insights.split('\n\n')
                
                # Display a success message
                st.success(f"✨ Local insights for {location} are ready!")
                
                # Create main content area with two columns
                col1, col2 = st.columns(2)
                
                # Cultural and Practical Information (Left Column)
                with col1:
                    st.markdown("### 🎌 Cultural & Practical Guide")
                    
                    # Local Customs Section
                    st.markdown("#### 👔 Local Customs & Etiquette")
                    st.info(sections[0])
                    
                    # Transportation Section
                    st.markdown("#### 🚆 Transportation Tips")
                    st.info(sections[1])
                    
                    # Language Section
                    st.markdown("#### 💬 Essential Local Phrases")
                    st.info(sections[2])
                    
                    # Safety Section
                    st.markdown("#### 🛡️ Safety Tips")
                    st.warning(sections[3])
                
                # Tourism and Food Information (Right Column)
                with col2:
                    st.markdown("### 🌟 Experience & Dining Guide")
                    
                    # Timing Section
                    st.markdown("#### ⏰ Best Times to Visit")
                    st.info(sections[4])
                    
                    # Food Section
                    st.markdown("#### 🍜 Local Food Guide")
                    st.success(sections[5])
                    
                    # Hidden Gems Section
                    st.markdown("#### 💎 Hidden Gems")
                    st.success(sections[6])
                
                # Add a download button for the insights
                st.divider()
                st.markdown("### 📥 Save Your Travel Guide")
                
                # Format the insights for download
                markdown_content = f"""# Local Travel Guide: {location}

## Cultural & Practical Information

### Local Customs & Etiquette
{sections[0]}

### Transportation Tips
{sections[1]}

### Essential Local Phrases
{sections[2]}

### Safety Tips
{sections[3]}

## Experience & Dining Guide

### Best Times to Visit
{sections[4]}

### Local Food Guide
{sections[5]}

### Hidden Gems
{sections[6]}
"""
                
                # Create download button
                st.download_button(
                    label="Download Travel Guide 📝",
                    data=markdown_content,
                    file_name=f"{location.replace(' ', '_')}_travel_guide.md",
                    mime="text/markdown"
                )
                
            except Exception as e:
                st.error(f"An error occurred while fetching local insights: {str(e)}")
    
    elif search_button and not location:
        st.warning("Please enter a destination to explore!")

def home():
    """Home page content"""
    st.title("Welcome to ExploreEase AI Travel Buddy 🌎")
    
    st.markdown("""
    ### Let AI Plan Your Perfect Trip! ✨
    
    ExploreEase helps you create personalized travel itineraries using artificial intelligence.
    Our smart system considers:
    
    - Optimal route planning 🗺️
    - Must-visit attractions 🏛️
    - Time-efficient scheduling ⏰
    - Location proximity 📍
    
    Ready to start planning? Select 'Plan a Trip' from the menu above!
    """)

def main():
    """Main application function"""
    # Sidebar with logo
    with st.sidebar:
        st.image("AI Travel Buddy.png", width=200)
        
        # Create the option menu
        selected = option_menu(
            "ExploreEase",
            ["Home", "Plan a Trip", "Local Insights"],
            icons=['house', 'map', 'chat-dots'],
            menu_icon="globe",
            default_index=0
        )
    
    # Display selected page
    # Display selected page
    if selected == "Home":
        home()
    elif selected == "Plan a Trip":
        plan_trip()
    elif selected == "Local Insights":
        local_insights()

if __name__ == "__main__":
    main()