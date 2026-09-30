---
name: weather
description: Look up current weather for any city (temperature, humidity, US AQI, wind speed). Use when the user asks for the weather, climate, AQI, humidity, or wind of a place, including prompts like "weather details of <city>".
---

# Weather

Use the **notes** MCP tool **get_weather**. Pass the city name from the user's prompt as `city`.

Do not invent temperature, humidity, AQI, or wind. If the city is missing from the prompt, ask which city.

## Report

After the tool returns, give:

- temperature in °C (`temperature_c`)
- humidity percent (`humidity_percent`)
- US AQI (`aqi`)
- wind speed in km/h (`wind_speed_kmh`)

Also mention the resolved city, country, and `observed_at`.

Bangalore temperature logging into the Current temperature note stays on `scripts/log_bangalore_temp.py`. A weather question is a lookup, not a note write, unless the user asks to log it.
