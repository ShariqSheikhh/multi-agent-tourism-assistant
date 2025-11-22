import streamlit as st
import requests
from typing import Optional, List
from dataclasses import dataclass

@dataclass
class Location:
    name: str
    latitude: float
    longitude: float
    display_name: str

@dataclass
class WeatherInfo:
    temperature: float
    rain_chance: float
    weather_code: int
    description: str

@dataclass
class Place:
    name: str
    type: str
    latitude: float
    longitude: float

class GeocodeAgent:
    def __init__(self):
        self.base_url = "https://nominatim.openstreetmap.org/search"
        self.headers = {'User-Agent': 'TourismApp/1.0'}
    
    def get_coordinates(self, place_name: str) -> Optional[Location]:
        try:
            params = {'q': place_name, 'format': 'json', 'limit': 1}
            response = requests.get(self.base_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            if not data:
                return None
            location_data = data[0]
            return Location(
                name=place_name,
                latitude=float(location_data['lat']),
                longitude=float(location_data['lon']),
                display_name=location_data['display_name']
            )
        except Exception as e:
            st.error(f"Geocoding error: {e}")
            return None

class WeatherAgent:
    def __init__(self):
        self.base_url = "https://api.open-meteo.com/v1/forecast"
    
    def get_weather(self, location: Location) -> Optional[WeatherInfo]:
        try:
            params = {
                'latitude': location.latitude,
                'longitude': location.longitude,
                'current': 'temperature_2m,weather_code',
                'daily': 'precipitation_probability_max',
                'timezone': 'auto'
            }
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            current = data.get('current', {})
            daily = data.get('daily', {})
            
            rain_chance = 0
            if 'precipitation_probability_max' in daily:
                rain_probs = daily['precipitation_probability_max']
                if rain_probs and len(rain_probs) > 0:
                    rain_chance = rain_probs[0]
            
            weather_code = current.get('weather_code', 0)
            description = self._get_weather_description(weather_code)
            
            return WeatherInfo(
                temperature=current.get('temperature_2m', 0),
                rain_chance=rain_chance,
                weather_code=weather_code,
                description=description
            )
        except Exception as e:
            st.error(f"Weather error: {e}")
            return None
    
    def _get_weather_description(self, code: int) -> str:
        weather_codes = {
            0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
            45: "foggy", 48: "foggy", 51: "light drizzle", 53: "moderate drizzle",
            55: "dense drizzle", 61: "slight rain", 63: "moderate rain",
            65: "heavy rain", 71: "slight snow", 73: "moderate snow",
            75: "heavy snow", 95: "thunderstorm"
        }
        return weather_codes.get(code, "unknown weather")

class PlacesAgent:
    def __init__(self):
        self.base_url = "https://overpass-api.de/api/interpreter"
    
    def get_tourist_attractions(self, location: Location, limit: int = 5) -> List[Place]:
        try:
            query = f"""
            [out:json][timeout:25];
            (
              node["tourism"~"attraction|museum|artwork|viewpoint|gallery"]
                (around:15000,{location.latitude},{location.longitude});
              way["tourism"~"attraction|museum|artwork|viewpoint|gallery"]
                (around:15000,{location.latitude},{location.longitude});
              node["historic"~"monument|castle|memorial|ruins"]
                (around:15000,{location.latitude},{location.longitude});
              way["historic"~"monument|castle|memorial|ruins"]
                (around:15000,{location.latitude},{location.longitude});
            );
            out center {limit * 3};
            """
            response = requests.post(self.base_url, data={'data': query}, timeout=30)
            response.raise_for_status()
            data = response.json()
            places = []
            seen_names = set()
            
            for element in data.get('elements', []):
                if 'lat' in element and 'lon' in element:
                    lat, lon = element['lat'], element['lon']
                elif 'center' in element:
                    lat, lon = element['center']['lat'], element['center']['lon']
                else:
                    continue
                
                tags = element.get('tags', {})
                name = tags.get('name', '')
                if not name or name in seen_names:
                    continue
                seen_names.add(name)
                
                attraction_type = tags.get('tourism', tags.get('historic', 'attraction'))
                places.append(Place(
                    name=name,
                    type=attraction_type.replace('_', ' ').title(),
                    latitude=lat,
                    longitude=lon
                ))
                if len(places) >= limit:
                    break
            return places
        except Exception as e:
            st.error(f"Places error: {e}")
            return []

class TourismParentAgent:
    def __init__(self):
        self.geocode_agent = GeocodeAgent()
        self.weather_agent = WeatherAgent()
        self.places_agent = PlacesAgent()
    
    def process_query(self, place_name: str, get_weather: bool, get_places: bool):
        with st.spinner(f'🔍 Looking up {place_name}...'):
            location = self.geocode_agent.get_coordinates(place_name)
        
        if not location:
            st.error(f"❌ I'm sorry, I don't know where '{place_name}' is. Please check the spelling.")
            return
        
        st.success(f"✅ Found: {location.display_name}")
        
        if get_weather:
            with st.spinner('🌤️ Fetching weather data...'):
                weather = self.weather_agent.get_weather(location)
            if weather:
                st.subheader("🌡️ Weather Information")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Temperature", f"{weather.temperature}°C")
                with col2:
                    st.metric("Conditions", weather.description.title())
                with col3:
                    st.metric("Rain Chance", f"{weather.rain_chance}%")
        
        if get_places:
            with st.spinner('🗺️ Finding tourist attractions...'):
                places = self.places_agent.get_tourist_attractions(location, limit=5)
            if places:
                st.subheader("🏛️ Top Tourist Attractions")
                for idx, place in enumerate(places, 1):
                    st.write(f"**{idx}. {place.name}** - *{place.type}*")
            else:
                st.warning("No specific tourist attractions found, but it's still worth exploring!")

def main():
    st.set_page_config(
        page_title="🌍 Tourism Assistant",
        page_icon="🌍",
        layout="wide"
    )
    
    st.title("🌍 Multi-Agent Tourism Assistant")
    st.markdown("*Your intelligent travel companion - Get weather info and tourist attraction recommendations!*")
    
    st.markdown("---")
    
    with st.sidebar:
        st.header("ℹ️ About")
        st.info("""
        This AI-powered system helps you plan your trips by providing:
        - 🌤️ Real-time weather data
        - 🗺️ Tourist attraction recommendations
        - 📍 Location information
        
        **Powered by:**
        - Multi-Agent Architecture
        - Deployed on Render
        """)
        
        st.header("🎯 Example Queries")
        st.code("Paris")
        st.code("Tokyo")
        st.code("Mumbai")
        st.code("London")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        place_name = st.text_input(
            "📍 Enter a destination:",
            placeholder="e.g., Paris, Tokyo, New York",
            help="Type any city or location you want to visit"
        )
    
    col1, col2 = st.columns(2)
    with col1:
        get_weather = st.checkbox("🌤️ Get Weather Information", value=True)
    with col2:
        get_places = st.checkbox("🗺️ Get Tourist Attractions", value=True)
    
    if st.button("🚀 Plan My Trip", type="primary", use_container_width=True):
        if place_name:
            agent = TourismParentAgent()
            agent.process_query(place_name, get_weather, get_places)
        else:
            st.warning("⚠️ Please enter a destination!")
    
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center'>
            <p>Made with ❤️ using Multi-Agent Architecture | Deployed on Render | 
            <a href='https://github.com/ShariqSheikhh/multi-agent-tourism-assistant'>GitHub</a>
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()