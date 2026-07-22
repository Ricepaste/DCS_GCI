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

local function round1(val)
    if not val then return 0 end
    return math.floor(val * 10 + 0.5) / 10
end

local function is_sam_or_threat(unit_type)
    if not unit_type then return false end
    local keywords = {
        "S-300", "SA-", "Patriot", "Hawk", "Avenger", "Linebacker", "Roland", "Gepard", "Vulcan",
        "Shilka", "Tunguska", "Tor", "Buk", "Kub", "Osa", "Strela", "Igla", "Stinger", "Chaparral",
        "Rapier", "HQ-", "EWR", "1L13", "55G6", "Dog Ear", "Flat Face", "Snow Drift", "Tin Shield",
        "Big Bird", "Clam Shell", "Flap Lid", "Tomb Stone", "S-75", "S-125", "S-200", "AAA", "SAM"
    }
    for _, k in ipairs(keywords) do
        if string.find(unit_type, k) then
            return true
        end
    end
    return false
end

-- 輔助函數：取得單位資料 (優化傳輸體積)
local function getUnitData(unit, is_friendly)
    if not unit or not unit:isExist() then return nil end
    local pos = unit:getPoint()
    if not pos then return nil end
    
    local category = -1
    local group = unit:getGroup()
    if group and group:isExist() then
        category = group:getCategory() or -1
    end
    
    local playerName = unit:getPlayerName() or ""
    local unitTypeName = unit:getTypeName() or ""
    
    -- 若為地面單位且既非玩家操控又非 SAM/防空威脅，直接過濾 (避免大量地面步兵與車輛超出 UDP 封包限制)
    if category == Group.Category.GROUND and playerName == "" then
        if not is_sam_or_threat(unitTypeName) then
            return nil
        end
    end

    local vel = unit:getVelocity() or {x=0, y=0, z=0}
    local unitName = unit:getName()
    local groupName = group and group:getName() or ""

    local fuel_frac = 0
    local fuel_mass_max_kg = 0
    if unit.getFuel then
        local f = unit:getFuel()
        if type(f) == "number" then fuel_frac = round1(f) end
    end
    if unit.getDesc then
        local desc = unit:getDesc()
        if desc and desc.fuelMassMax then
            fuel_mass_max_kg = math.floor(desc.fuelMassMax)
        end
    end
    
    local weapons = {}
    if playerName ~= "" and unit.getAmmo then
        local ammo = unit:getAmmo()
        if ammo and type(ammo) == "table" then
            for _, item in pairs(ammo) do
                local w_name = "Unknown"
                if item.desc then
                    w_name = item.desc.displayName or item.desc.typeName or w_name
                end
                table.insert(weapons, {name = w_name, count = item.count or 0})
            end
        end
    end

    return {
        unit_name = unitName,
        player_name = playerName,
        group_name = groupName,
        category = category,
        type = unitTypeName,
        x = round1(pos.x),
        y = round1(pos.y),
        z = round1(pos.z),
        vx = round1(vel.x),
        vy = round1(vel.y),
        vz = round1(vel.z),
        is_friendly = is_friendly,
        fuel_frac = fuel_frac,
        fuel_mass_max_kg = fuel_mass_max_kg,
        weapons = weapons
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
    local ab_list = world.getAirbases()
    if ab_list then
        for _, airbase in pairs(ab_list) do
            if airbase and airbase:isExist() then
                local p = airbase:getPoint()
                if p then
                    local lat, lon = coord.LOtoLL(p)
                    table.insert(airbases_data, {
                        name = airbase:getName(),
                        x = round1(p.x),
                        z = round1(p.z),
                        lat = round1(lat),
                        lon = round1(lon)
                    })
                end
            end
        end
    end
    return airbases_data
end

local function get_telemetry_for_coalition(friendly_side, enemy_side)
    local telemetry = {
        friendlies = {},
        hostiles = {}
    }
    local knownHostiles = {}
    local categories = {Group.Category.AIRPLANE, Group.Category.HELICOPTER, Group.Category.GROUND}
    for _, cat in ipairs(categories) do
        local friendlyGroups = coalition.getGroups(friendly_side, cat)
        if friendlyGroups then
            for _, group in pairs(friendlyGroups) do
                if group and group:isExist() then
                    -- 1. 抓取所有本方單位的位置
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
                    
                    -- 2. 讓本方雷達網抓取敵方單位
                    local controller = group:getController()
                    if controller then
                        local targets = controller:getDetectedTargets()
                        if targets then
                            for _, targetData in pairs(targets) do
                                local enemyUnit = targetData.object
                                if enemyUnit and enemyUnit:isExist() and enemyUnit.getCoalition and enemyUnit:getCoalition() == enemy_side then
                                    local uid = enemyUnit:getName()
                                    local is_distance_known = targetData.distance
                                    
                                    if not knownHostiles[uid] then
                                        knownHostiles[uid] = {
                                            unit = enemyUnit,
                                            is_jammed = not is_distance_known,
                                            detected_by = {}
                                        }
                                    else
                                        if is_distance_known then
                                            knownHostiles[uid].is_jammed = false
                                        end
                                    end
                                    
                                    -- 如果仍在被干擾中，記錄是哪些單位探測到這個干擾源
                                    if knownHostiles[uid].is_jammed then
                                        local first_unit = group:getUnit(1)
                                        if first_unit and first_unit:isExist() then
                                            table.insert(knownHostiles[uid].detected_by, first_unit:getName())
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
    
    for uid, info in pairs(knownHostiles) do
        local data = getUnitData(info.unit, false)
        if data then
            data.is_jammed = info.is_jammed
            if info.is_jammed then
                data.jammed_by = info.detected_by
            end
            table.insert(telemetry.hostiles, data)
        end
    end
    
    return telemetry
end

local function export_telemetry_safe(time, args)
    local status, err = pcall(function()
        local airbases = get_airbases()
        local blue_telemetry = get_telemetry_for_coalition(coalition.side.BLUE, coalition.side.RED)
        local red_telemetry = get_telemetry_for_coalition(coalition.side.RED, coalition.side.BLUE)
        
        -- 分拆為藍軍與紅軍獨立 UDP 封包發送 (防止單一 UDP 封包超出一 64KB 限制)
        local packet_blue = encode_json({
            blue = blue_telemetry,
            friendlies = blue_telemetry.friendlies,
            hostiles = blue_telemetry.hostiles,
            airbases = airbases
        })
        udp:sendto(packet_blue, UDP_IP, UDP_PORT)
        
        local packet_red = encode_json({
            red = red_telemetry,
            airbases = airbases
        })
        udp:sendto(packet_red, UDP_IP, UDP_PORT)
    end)
    
    if not status then
        env.info("GCI Exporter Error: " .. tostring(err))
    end
    
    return timer.getTime() + UPDATE_INTERVAL
end

timer.scheduleFunction(export_telemetry_safe, nil, timer.getTime() + UPDATE_INTERVAL)
env.info("Pure DCS API External GCI Exporter Started!")
