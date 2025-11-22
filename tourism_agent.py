import requests
import json
from typing import Dict, List, Optional
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
    """Agent responsible for converting place names to coordinates"""
    
    def __init__(self):
        self.base_url = "https://nominatim.openstreetmap.org/search"
        self.headers = {
            'User-Agent': 'TourismApp/1.0'
        }
    
    def get_coordinates(self, place_name: str) -> Optional[Location]:
        """Get coordinates for a place name"""
        try:
            params = {
                'q': place_name,
                'format': 'json',
                'limit': 1
            }
            
            response = requests.get(
                self.base_url, 
                params=params, 
                headers=self.headers,
                timeout=10
            )
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
            print(f"Geocoding error: {e}")
            return None

class WeatherAgent:
    """Agent responsible for fetching weather information"""
    
    def __init__(self):
        self.base_url = "https://api.open-meteo.com/v1/forecast"
    
    def get_weather(self, location: Location) -> Optional[WeatherInfo]:
        """Get current weather for a location"""
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
            
            # Get precipitation probability from daily forecast
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
            print(f"Weather error: {e}")
            return None
    
    def _get_weather_description(self, code: int) -> str:
        """Convert weather code to description"""
        weather_codes = {
            0: "clear sky",
            1: "mainly clear",
            2: "partly cloudy",
            3: "overcast",
            45: "foggy",
            48: "foggy",
            51: "light drizzle",
            53: "moderate drizzle",
            55: "dense drizzle",
            61: "slight rain",
            63: "moderate rain",
            65: "heavy rain",
            71: "slight snow",
            73: "moderate snow",
            75: "heavy snow",
            77: "snow grains",
            80: "slight rain showers",
            81: "moderate rain showers",
            82: "violent rain showers",
            85: "slight snow showers",
            86: "heavy snow showers",
            95: "thunderstorm",
            96: "thunderstorm with slight hail",
            99: "thunderstorm with heavy hail"
        }
        return weather_codes.get(code, "unknown weather")

class PlacesAgent:
    """Agent responsible for finding tourist attractions"""
    
    def __init__(self):
        self.base_url = "https://overpass-api.de/api/interpreter"
    
    def get_tourist_attractions(self, location: Location, limit: int = 5) -> List[Place]:
        """Get tourist attractions near a location"""
        try:
            # Overpass query to find tourist attractions
            query = f"""
            [out:json][timeout:25];
            (
              node["tourism"~"attraction|museum|artwork|viewpoint|gallery"]
                (around:15000,{location.latitude},{location.longitude});
              way["tourism"~"attraction|museum|artwork|viewpoint|gallery"]
                (around:15000,{location.latitude},{location.longitude});
              node["historic"~"monument|castle|memorial|ruins|archaeological_site"]
                (around:15000,{location.latitude},{location.longitude});
              way["historic"~"monument|castle|memorial|ruins|archaeological_site"]
                (around:15000,{location.latitude},{location.longitude});
            );
            out center {limit * 3};
            """
            
            response = requests.post(
                self.base_url,
                data={'data': query},
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            places = []
            seen_names = set()
            
            for element in data.get('elements', []):
                # Get coordinates
                if 'lat' in element and 'lon' in element:
                    lat, lon = element['lat'], element['lon']
                elif 'center' in element:
                    lat, lon = element['center']['lat'], element['center']['lon']
                else:
                    continue
                
                tags = element.get('tags', {})
                name = tags.get('name', '')
                
                # Skip unnamed attractions or duplicates
                if not name or name in seen_names:
                    continue
                
                seen_names.add(name)
                
                # Get type of attraction
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
            print(f"Places error: {e}")
            return []

class TourismParentAgent:
    """Main orchestrating agent that coordinates child agents"""
    
    def __init__(self):
        self.geocode_agent = GeocodeAgent()
        self.weather_agent = WeatherAgent()
        self.places_agent = PlacesAgent()
    
    def process_query(self, user_input: str) -> str:
        """Process user query and coordinate agents"""
        
        # Analyze user intent using rule-based approach
        intent = self._analyze_intent(user_input)
        
        place_name = intent['place']
        needs_weather = intent['needs_weather']
        needs_places = intent['needs_places']
        
        if not place_name:
            return "I couldn't identify which place you're asking about. Please mention a specific location. For example: 'I'm going to Paris' or 'What's the weather in Tokyo?'"
        
        # Step 1: Geocode the place
        print(f"🔍 Looking up location: {place_name}...")
        location = self.geocode_agent.get_coordinates(place_name)
        
        if not location:
            return f"I'm sorry, I don't know where '{place_name}' is. It doesn't seem to exist in my database. Could you please check the spelling or try a different place?"
        
        response_parts = []
        
        # Step 2: Get weather if needed
        if needs_weather:
            print(f"🌤️  Fetching weather data...")
            weather = self.weather_agent.get_weather(location)
            if weather:
                weather_text = f"In {place_name}, it's currently {weather.temperature}°C with {weather.description} and a {weather.rain_chance}% chance of rain."
                response_parts.append(weather_text)
            else:
                response_parts.append(f"I couldn't fetch weather information for {place_name} at the moment.")
        
        # Step 3: Get places if needed
        if needs_places:
            print(f"🗺️  Finding tourist attractions...")
            places = self.places_agent.get_tourist_attractions(location, limit=5)
            
            if places:
                places_text = f"Here are some great places you can visit in {place_name}:"
                for idx, place in enumerate(places, 1):
                    places_text += f"\n  {idx}. {place.name} ({place.type})"
                response_parts.append(places_text)
            else:
                response_parts.append(f"I couldn't find specific tourist attractions in {place_name}, but it's still worth exploring!")
        
        if response_parts:
            return "\n\n".join(response_parts)
        else:
            return f"I found {place_name}, but I'm not sure what information you need. You can ask about weather or places to visit!"
    
    def _analyze_intent(self, user_input: str) -> Dict:
        """Analyze user intent using rule-based keyword matching"""
        
        user_lower = user_input.lower()
        
        # Extract place name
        place = self._extract_place(user_input, user_lower)
        
        # Check for weather-related keywords
        weather_keywords = [
            'weather', 'temperature', 'temp', 'rain', 'hot', 'cold', 
            'climate', 'forecast', 'sunny', 'cloudy', 'warm', 'cool',
            'degrees', 'celsius', 'fahrenheit'
        ]
        needs_weather = any(keyword in user_lower for keyword in weather_keywords)
        
        # Check for places-related keywords
        places_keywords = [
            'places', 'visit', 'attractions', 'see', 'trip', 'plan',
            'go', 'tourist', 'sights', 'recommendations', 'where',
            'what to do', 'things to do', 'explore', 'tourism'
        ]
        needs_places = any(keyword in user_lower for keyword in places_keywords)
        
        # Special case: if they say "plan my trip", show both
        if 'plan' in user_lower and 'trip' in user_lower:
            needs_places = True
        
        # If nothing specific is mentioned but they mention a place, show places
        if not needs_weather and not needs_places and place:
            needs_places = True
        
        return {
            'place': place,
            'needs_weather': needs_weather,
            'needs_places': needs_places
        }
    
    def _extract_place(self, user_input: str, user_lower: str) -> str:
        """Extract place name from user input"""
        
        # Common patterns to look for
        patterns = [
            ('going to ', ' going to '),
            ('go to ', ' go to '),
            ('visit ', ' visit '),
            ('in ', ' in '),
            ('to ', ' to '),
            ('travel to ', ' travel to '),
            ('trip to ', ' trip to '),
            ('headed to ', ' headed to '),
            ('flying to ', ' flying to '),
        ]
        
        # Try each pattern
        for pattern, search_pattern in patterns:
            if search_pattern in f" {user_lower} ":
                # Extract text after the pattern
                idx = user_lower.find(search_pattern) + len(search_pattern)
                after_pattern = user_input[idx:]
                
                # Stop at common delimiters
                delimiters = [',', '?', '.', '!', ' and ', ' what ', ' let', ' how', ' when', ' where']
                for delimiter in delimiters:
                    if delimiter in after_pattern.lower():
                        after_pattern = after_pattern[:after_pattern.lower().find(delimiter)]
                
                place = after_pattern.strip()
                if place:
                    return place
        
        # Fallback: look for capitalized words (likely place names)
        words = user_input.split()
        capitalized = []
        skip_words = {'I', 'I\'m', 'What', 'Where', 'How', 'When', 'Can', 'Could', 'Should', 'Would', 'The'}
        
        for word in words:
            word_clean = word.strip(',.?!\'"')
            if word_clean and word_clean[0].isupper() and word_clean not in skip_words:
                capitalized.append(word_clean)
        
        if capitalized:
            return ' '.join(capitalized)
        
        return ""

def main():
    """Main function to run the tourism agent"""
    
    print("=" * 60)
    print("🌍 Welcome to the Multi-Agent Tourism System!")
    print("=" * 60)
    print("\nYou can ask me about:")
    print("  • Weather in a location")
    print("  • Tourist attractions to visit")
    print("  • Or both!\n")
    print("Examples:")
    print("  - I'm going to Paris, let's plan my trip")
    print("  - What's the temperature in Tokyo?")
    print("  - I want to visit London, what's the weather and what can I see?")
    print("\nType 'exit' to quit.\n")
    print("=" * 60)
    
    agent = TourismParentAgent()
    
    while True:
        print("\n" + "-" * 60)
        user_input = input("\n👤 You: ").strip()
        
        if user_input.lower() in ['exit', 'quit', 'bye', 'q']:
            print("\n👋 Thanks for using Tourism AI Agent! Safe travels!")
            break
        
        if not user_input:
            continue
        
        print("\n🤖 Processing your request...")
        print("-" * 60)
        
        response = agent.process_query(user_input)
        
        print(f"\n✨ Tourism Agent:\n{response}")

if __name__ == "__main__":
    main()