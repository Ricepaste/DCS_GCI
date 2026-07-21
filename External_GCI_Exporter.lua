env.info("External GCI Exporter Loading...")

local UDP_IP = "127.0.0.1"
local UDP_PORT = 10088
local UPDATE_INTERVAL = 4.0 -- 4s (Link 16 / AESA update rate)

-- Setup UDP Socket
package.path  = package.path..";.\\LuaSocket\\?.lua"
package.cpath = package.cpath..";.\\LuaSocket\\?.dll"
local socket = require("socket")
local udp = socket.udp()
udp:settimeout(0)

-- 輔助函數：取得單位資料
local function getUnitData(unit, is_friendly)
    if not unit or not unit:isExist() then return nil end
    local pos = unit:getPoint()
    local vel = unit:getVelocity()
    local heading = 0
    
    -- Calculate heading from velocity vector
    if vel.x ~= 0 or vel.z ~= 0 then
        heading = math.atan2(vel.z, vel.x)
    end

    local playerName = unit:getPlayerName()
    local unitName = unit:getName()
    
    local lat, lon, alt = coord.LOtoLL(pos)

    return {
        unit_name = unitName,
        player_name = playerName or "",
        group_name = unit:getGroup():getName(),
        type = unit:getTypeName(),
        x = pos.x,
        y = pos.y, -- altitude in DCS
        z = pos.z,
        lat = lat,
        lon = lon,
        vx = vel.x,
        vy = vel.y,
        vz = vel.z,
        heading = heading,
        is_friendly = is_friendly
    }
end

-- 簡易的 JSON Encoder
local function encode_json(val)
    local t = type(val)
    if t == "number" then return string.gsub(tostring(val), ",", ".")
    elseif t == "boolean" then return tostring(val)
    elseif t == "string" then return string.format("%q", val)
    elseif t == "table" then
        local isArray = true
        local n = 0
        for k, v in pairs(val) do
            n = n + 1
            if type(k) ~= "number" or k ~= n then
                isArray = false
                break
            end
        end
        if isArray then
            local items = {}
            for i = 1, #val do table.insert(items, encode_json(val[i])) end
            return "[" .. table.concat(items, ",") .. "]"
        else
            local items = {}
            for k, v in pairs(val) do
                table.insert(items, string.format("%q:%s", tostring(k), encode_json(v)))
            end
            return "{" .. table.concat(items, ",") .. "}"
        end
    end
    return "null"
end

local function get_airbases()
    local airbases_data = {}
    for _, airbase in pairs(world.getAirbases()) do
        local p = airbase:getPoint()
        local lat, lon = coord.LOtoLL(p)
        table.insert(airbases_data, {
            name = airbase:getName(),
            x = p.x,
            z = p.z,
            lat = lat,
            lon = lon
        })
    end
    return airbases_data
end

local function export_telemetry_safe(time, args)
    local telemetry = {
        friendlies = {},
        hostiles = {},
        airbases = get_airbases()
    }
    
    local knownHostiles = {}
    
    local categories = {Group.Category.AIRPLANE, Group.Category.HELICOPTER}
    for _, cat in ipairs(categories) do
        local blueGroups = coalition.getGroups(coalition.side.BLUE, cat)
        if blueGroups then
            for _, group in pairs(blueGroups) do
                if group and group:isExist() then
                    -- 1. 抓取所有藍軍單位的位置
                    local units = group:getUnits()
                    if units then
                        for _, unit in pairs(units) do
                            if unit and unit:isExist() then
                                local data = getUnitData(unit, true)
                                if data then
                                    table.insert(telemetry.friendlies, data)
                                end
                            end
                        end
                    end
                    
                    -- 2. 讓藍軍雷達網抓取紅軍單位
                    local controller = group:getController()
                    if controller then
                        local targets = controller:getDetectedTargets()
                        if targets then
                            for _, targetData in pairs(targets) do
                                local enemyUnit = targetData.object
                                if enemyUnit and enemyUnit:isExist() and enemyUnit.getCoalition and enemyUnit:getCoalition() == coalition.side.RED then
                                    local uid = enemyUnit:getName()
                                    if not knownHostiles[uid] then
                                        knownHostiles[uid] = true
                                        local data = getUnitData(enemyUnit, false)
                                        if data then
                                            table.insert(telemetry.hostiles, data)
                                        end
                                    end
                                end
                            end
                        end
                    end
                end
            end
        end
    end
    
    local jsonStr = encode_json(telemetry)
    udp:sendto(jsonStr, UDP_IP, UDP_PORT)
    
    return timer.getTime() + UPDATE_INTERVAL
end

timer.scheduleFunction(export_telemetry_safe, nil, timer.getTime() + UPDATE_INTERVAL)
env.info("Pure DCS API External GCI Exporter Started!")
