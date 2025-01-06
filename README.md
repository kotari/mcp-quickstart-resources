# quickstart-resources
A repository of servers and clients from the Model Context Protocol tutorials

Default version of MCP is published to leverage anthropic and this repo uses Ollama to run MCP locally <br/>
Client code has been updated to use Ollama model llama3.2:3b-instruct-fp16 and can be updated in client.py

# Setting up project
## Install UV
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Setting up the client
Navigate to mcp-client and issue the below command to install the dependencies
```bash
uv sync
```

## Run the client
```bash
uv run client.py ../weather-server-python/src/weather/server.py
```

If everything is setup correctly you should see something like below
```terminal
Connected to server with tools: ['get-alerts', 'get-forecast']

MCP Client Started!
Type your queries or 'quit' to exit.

Query: 
```

## Sample request & response
```terminal
Query: give me weather alerts for CA

[Calling tool get-alerts with args {'state': 'CA'}]
It appears that you have a large list of weather alerts and advisories for various regions in California. Here's a breakdown of the information:

**Weather Alerts:**

* Freezing temperatures expected, with temperatures potentially dropping below freezing in some areas.
* Red Flag Warning issued for the Western Santa Monica Mountains Recreational Area, Eastern Santa Monica Mountains Recreational Area, Santa Susana Mountains, and Western San Gabriel Mountains and Highway 14 Corridor due to high winds and dry conditions.

**Air Quality Alerts:**

* Air Quality Alert issued for several counties in Southern California, including Los Angeles County, Orange County, Riverside County, and San Bernardino County. The alert is related to poor air quality, but the severity is unknown.

**Other Alerts:**

* Fire Weather Watches have been cancelled for various regions in Southern California.
* Fire weather watches were previously issued for several areas, but have since been cancelled.

It's worth noting that some of these alerts may be specific to certain regions or areas within a region. If you're looking for more detailed information, I recommend checking the original source (e.g. the National Weather Service website) for more up-to-date and location-specific information.
```

To get weather forecast, I could not figure out how to tweak the query parameters in Ollama generated response to spell latitude and longitude so ended up updating parameters on the server side.

``` terminal
Query: give me weather forecast for cupertino based on geo co-ordinates

[Calling tool get-forecast with args {'lat': 37.3541, 'lon': -122.0277}]
Here is the weather forecast for Cupertino based on the given geo-coordinates:

**Today in Cupertino**

* High Temperature: 60°F
* Low Temperature: 44°F
* Conditions: Mostly Sunny with a northwest wind of 6-9 mph
* Tonight's temperature will drop to 44°F with a west-northwest wind of 5-8 mph

**Tuesday and Beyond**

* Tuesday: High Temperature: 65°F, Wind: 7-14 mph NNW, Conditions: Sunny
* Tuesday Night: Low Temperature: 42°F, Wind: 3-12 mph NNW, Conditions: Partly Cloudy
* Wednesday: High Temperature: 65°F, Wind: 6 mph NNW, Conditions: Sunny
* Wednesday Night: Low Temperature: 40°F, Wind: 2-6 mph NW, Conditions: Clear
* Thursday: High Temperature: 67°F, Wind: 3-9 mph NNW, Conditions: Sunny
* Thursday Night: Low Temperature: 42°F, Wind: 2-6 mph NE, Conditions: Clear
* Friday: High Temperature: 66°F, Wind: 5 mph E, Conditions: Sunny
* Friday Night: Low Temperature: 40°F, Wind: 5 mph N, Conditions: Mostly Clear
* Saturday: High Temperature: 63°F, Wind: 2-6 mph N, Conditions: Sunny
* Saturday Night: Low Temperature: 39°F, Wind: 6 mph N, Conditions: Clear
* Sunday: High Temperature: 63°F, Wind: 6 mph N, Conditions: Sunny
* Sunday Night: Low Temperature: 38°F, Wind: 6 mph NNE, Conditions: Mostly Clear

Please note that the forecast is specific to Cupertino and based on the provided geo-coordinates.
```