--- TopGun AI Logic Bridge
-- This script bridges DCS with an external Python Behavior Tree via UDP sockets.
-- It depends on MOOSE for easier group management, but uses luasocket for networking.

env.info("TopGun AI Logic Bridge: Loading...")

package.path  = package.path..";.\\LuaSocket\\?.lua"
package.cpath = package.cpath..";.\\LuaSocket\\?.dll"
local socket = require("socket")
local JSON = loadfile("Scripts\\JSON.lua")() -- DCS usually has a JSON parser or we can use MOOSE json

-- Networking Setup
local UDP_IP_SEND = "127.0.0.1"
local UDP_PORT_SEND = 10080
local UDP_IP_LISTEN = "127.0.0.1"
local UDP_PORT_LISTEN = 10081

local sendSocket = socket.udp()
local receiveSocket = socket.udp()
receiveSocket:setsockname(UDP_IP_LISTEN, UDP_PORT_LISTEN)
receiveSocket:settimeout(0.001) -- Non-blocking

-- Helper: serialize simple table to JSON string manually since DCS JSON can be tricky
local function basicJSONEncode(tbl)
    -- very simplified encoder for demonstration
    local str = "{"
    for k, v in pairs(tbl) do
        str = str .. '"' .. tostring(k) .. '":'
        if type(v) == "string" then
            str = str .. '"' .. v .. '"'
        elseif type(v) == "boolean" then
            str = str .. tostring(v)
        elseif type(v) == "number" then
            str = str .. tostring(v)
        elseif type(v) == "table" then
            -- Note: assuming array of objects for 'units'
            str = str .. "["
            for i, item in ipairs(v) do
                str = str .. basicJSONEncode(item)
                if i < #v then str = str .. "," end
            end
            str = str .. "]"
        end
        str = str .. ","
    end
    -- remove last comma
    if string.sub(str, -1) == "," then
        str = string.sub(str, 1, -2)
    end
    str = str .. "}"
    return str
end

-- Telemetry Sender Loop
local function SendTelemetry()
    -- Get groups to manage, for example all groups with 'Red_AI' in name
    local managedGroups = SET_GROUP:New():FilterPrefixes("Red_AI"):FilterActive():FilterStart()
    
    managedGroups:ForEachGroup(function(grp)
        if grp:IsAlive() then
            local lead = grp:GetUnit(1)
            if lead and lead:IsAlive() then
                local data = {
                    group_name = grp:GetName(),
                    units = {
                        {
                            name = lead:GetName(),
                            is_locked = lead:GetRadarWarning() ~= nil, -- Simplified
                            has_missile_in_air = false -- Needs S_EVENT_SHOT tracking to be accurate
                        }
                    }
                }
                
                local jsonStr = basicJSONEncode(data)
                sendSocket:sendto(jsonStr, UDP_IP_SEND, UDP_PORT_SEND)
            end
        end
    end)
    
    return timer.getTime() + 0.5 -- run every 0.5 sec
end

timer.scheduleFunction(SendTelemetry, nil, timer.getTime() + 1)

-- Command Receiver Loop
local function ReceiveCommands()
    local data, err = receiveSocket:receive()
    if data then
        env.info("TopGun AI Bridge Received: " .. data)
        -- Parsing logic goes here (use JSON decoder)
        -- e.g. execute Crank or Pump based on 'data'
    end
    return timer.getTime() + 0.1 -- run every 0.1 sec
end

timer.scheduleFunction(ReceiveCommands, nil, timer.getTime() + 1)

env.info("TopGun AI Logic Bridge: Loaded successfully.")
