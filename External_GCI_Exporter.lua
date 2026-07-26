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
        "S-300", "SA-", "Patriot", "Hawk", "NASAMS", "Avenger", "Linebacker", "Roland", "Gepard", "Vulcan",
        "Shilka", "Tunguska", "Tor", "Buk", "Kub", "Osa", "Strela", "Igla", "Stinger", "Chaparral",
        "Rapier", "HQ-", "EWR", "1L13", "55G6", "Dog Ear", "Flat Face", "Snow Drift", "Tin Shield",
        "Big Bird", "Clam Shell", "Flap Lid", "Tomb Stone", "S-75", "S-125", "S-200", "AAA", "SAM",
        "Pyotr", "Slava", "Ticonderoga", "Arleigh", "Oliver", "Type 052", "Type 054", "Sea Sparrow"
    }
    for _, k in ipairs(keywords) do
        if string.find(unit_type, k) then
            return true
        end
    end
    return false
end

-- 安全取值 Helper (完全相容 Unit, Weapon, StaticObject, Ship, Building)
local function getSafeName(obj)
    if not obj or not obj:isExist() then return nil end
    local name = nil
    if obj.getName then
        pcall(function() name = obj:getName() end)
    end
    if name and name ~= "" then return name end
    
    local typeName = "Unknown"
    if obj.getTypeName then
        pcall(function() typeName = obj:getTypeName() end)
    end
    
    local id = nil
    if obj.getID then
        pcall(function() id = obj:getID() end)
    end
    if id then
        return typeName .. "_" .. tostring(id)
    end
    return typeName .. "_" .. tostring(obj)
end

local function getSafeTypeName(obj)
    if not obj or not obj:isExist() then return "" end
    if obj.getTypeName then
        local status, tn = pcall(function() return obj:getTypeName() end)
        if status and tn then return tn end
    end
    return ""
end

local function getSafePlayerName(obj)
    if not obj or not obj:isExist() then return "" end
    if obj.getPlayerName then
        local status, pn = pcall(function() return obj:getPlayerName() end)
        if status and pn then return pn end
    end
    return ""
end

local function getSafeCategory(obj)
    if not obj or not obj:isExist() then return -1 end
    if obj.getGroup then
        local status, g = pcall(function() return obj:getGroup() end)
        if status and g and g:isExist() and g.getCategory then
            local status_c, cat = pcall(function() return g:getCategory() end)
            if status_c and cat then return cat end
        end
    end
    if obj.getCategory then
        local status, cat = pcall(function() return obj:getCategory() end)
        if status and cat then return cat end
    end
    return -1
end

-- 輔助函數：取得單位資料 (相容 飛機/海軍/防空/巡弋飛彈/武器物件)
local function getUnitData(unit, is_friendly)
    if not unit or not unit:isExist() then return nil end
    if not unit.getPoint then return nil end
    
    local status_p, pos = pcall(function() return unit:getPoint() end)
    if not status_p or not pos then return nil end
    
    local category = getSafeCategory(unit)
    local playerName = getSafePlayerName(unit)
    local unitTypeName = getSafeTypeName(unit)
    
    -- 若為地面單位且既非玩家操控又非 SAM/防空威脅，直接過濾 (避免大量地面步兵與車輛超出 UDP 封包限制)
    if category == Group.Category.GROUND and playerName == "" then
        if not is_sam_or_threat(unitTypeName) then
            return nil
        end
    end

    local vel = {x=0, y=0, z=0}
    if unit.getVelocity then
        local status_v, v = pcall(function() return unit:getVelocity() end)
        if status_v and v then vel = v end
    end
    
    local unitName = getSafeName(unit) or "Track"
    local groupName = ""
    if unit.getGroup then
        local status_g, group = pcall(function() return unit:getGroup() end)
        if status_g and group and group:isExist() and group.getName then
            local status_gn, gn = pcall(function() return group:getName() end)
            if status_gn and gn then groupName = gn end
        end
    end

    local fuel_frac = 0
    local fuel_mass_max_kg = 0
    if unit.getFuel then
        local status_f, f = pcall(function() return unit:getFuel() end)
        if status_f and type(f) == "number" then fuel_frac = round1(f) end
    end
    if unit.getDesc then
        local status_d, desc = pcall(function() return unit:getDesc() end)
        if status_d and desc and desc.fuelMassMax then
            fuel_mass_max_kg = math.floor(desc.fuelMassMax)
        end
    end
    
    local weapons = {}
    if unit.getAmmo then
        local status_a, ammo = pcall(function() return unit:getAmmo() end)
        if status_a and ammo and type(ammo) == "table" then
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
    local status_ab, ab_list = pcall(function() return world.getAirbases() end)
    if status_ab and ab_list then
        for _, airbase in pairs(ab_list) do
            if airbase and airbase:isExist() then
                local status_p, p = pcall(function() return airbase:getPoint() end)
                if status_p and p then
                    local lat, lon = 0, 0
                    pcall(function() lat, lon = coord.LOtoLL(p) end)
                    local name = getSafeName(airbase) or "Airbase"
                    table.insert(airbases_data, {
                        name = name,
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
    -- 加入 Group.Category.SHIP (海軍艦艇)
    local categories = {Group.Category.AIRPLANE, Group.Category.HELICOPTER, Group.Category.GROUND, Group.Category.SHIP}
    for _, cat in ipairs(categories) do
        local status_g, friendlyGroups = pcall(function() return coalition.getGroups(friendly_side, cat) end)
        if status_g and friendlyGroups then
            for _, group in pairs(friendlyGroups) do
                if group and group:isExist() then
                    -- 1. 抓取所有本方單位的位置
                    local status_u, units = pcall(function() return group:getUnits() end)
                    if status_u and units then
                        for _, unit in pairs(units) do
                            if unit and unit:isExist() then
                                local data = getUnitData(unit, true)
                                if data then
                                    table.insert(telemetry.friendlies, data)
                                end
                            end
                        end
                    end
                    
                    -- 2. 讓本方雷達網抓取敵方單位 (包含飛彈/武器/艦艇 Target)
                    local status_ctrl, controller = pcall(function() return group:getController() end)
                    if status_ctrl and controller then
                        local status_t, targets = pcall(function() return controller:getDetectedTargets() end)
                        if status_t and targets then
                            for _, targetData in pairs(targets) do
                                local enemyUnit = targetData.object
                                if enemyUnit and enemyUnit:isExist() then
                                    local enemy_coalition = -1
                                    if enemyUnit.getCoalition then
                                        pcall(function() enemy_coalition = enemyUnit:getCoalition() end)
                                    end
                                    
                                    if enemy_coalition ~= friendly_side or enemy_coalition == -1 then
                                        local uid = getSafeName(enemyUnit)
                                        if uid and uid ~= "" then
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
                                                local status_fu, first_unit = pcall(function() return group:getUnit(1) end)
                                                if status_fu and first_unit and first_unit:isExist() then
                                                    local fname = getSafeName(first_unit)
                                                    if fname then
                                                        table.insert(knownHostiles[uid].detected_by, fname)
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
            end
        end
    end
    
    -- 2. 抓取所有非本方陣營 (包含中立 0 / NEUTRAL、敵軍 1/2) 的所有群組與單位，歸類為 hostiles (預設 UNKNOWN)
    local neutral_side = 0
    if coalition and type(coalition.side) == "table" and coalition.side.NEUTRAL then
        neutral_side = coalition.side.NEUTRAL
    end
    local all_sides = {0, 1, 2, neutral_side, enemy_side}
    local scanned = {}
    for _, side_id in ipairs(all_sides) do
        if side_id and side_id ~= friendly_side and not scanned[side_id] then
            scanned[side_id] = true
            for _, cat in ipairs(categories) do
                pcall(function()
                    local otherGroups = coalition.getGroups(side_id, cat)
                    if otherGroups then
                        for _, group in pairs(otherGroups) do
                            if group and group:isExist() then
                                local units = group:getUnits()
                                if units then
                                    for _, unit in pairs(units) do
                                        if unit and unit:isExist() then
                                            local uid = getSafeName(unit)
                                            if uid and uid ~= "" and not knownHostiles[uid] then
                                                knownHostiles[uid] = {
                                                    unit = unit,
                                                    is_jammed = false,
                                                    detected_by = {}
                                                }
                                            end
                                        end
                                    end
                                end
                            end
                        end
                    end
                end)
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

-- Setup UDP Command Listening Socket (Port 10089)
local cmd_udp = socket.udp()
cmd_udp:setsockname("*", 10089)
cmd_udp:settimeout(0)

local spawn_count = 0

local function process_incoming_commands()
    while true do
        local data, ip, port = cmd_udp:receivefrom()
        if not data then break end
        
        local status_run, err = pcall(function()
            local cmd = nil
            if net and net.json2lua then
                cmd = net.json2lua(data)
            else
                local action = data:match('"action"%s*:%s*"([^"]+)"')
                if action then
                    cmd = { action = action }
                    cmd.group_name = data:match('"group_name"%s*:%s*"([^"]+)"')
                    cmd.target_name = data:match('"target_name"%s*:%s*"([^"]+)"')
                    cmd.roe_mode = data:match('"roe_mode"%s*:%s*"([^"]+)"')
                    cmd.unit_type = data:match('"unit_type"%s*:%s*"([^"]+)"')
                    cmd.side = data:match('"side"%s*:%s*"([^"]+)"')
                    cmd.x = tonumber(data:match('"x"%s*:%s*([%d%.%-]+)'))
                    cmd.z = tonumber(data:match('"z"%s*:%s*([%d%.%-]+)'))
                end
            end
            
            if not cmd or not cmd.action then return end
            
            if env and env.info then
                env.info(string.format("[GCI CMD LOG] Received action='%s', group='%s', target='%s', roe='%s', x=%s, z=%s",
                    tostring(cmd.action), tostring(cmd.group_name), tostring(cmd.target_name), tostring(cmd.roe_mode), tostring(cmd.x), tostring(cmd.z)))
            end
            
            if cmd.action == "vector" and cmd.group_name and cmd.x and cmd.z then
                local grp = Group.getByName(cmd.group_name) or (Unit.getByName(cmd.group_name) and Unit.getByName(cmd.group_name):getGroup())
                if grp and grp:isExist() then
                    local controller = grp:getController()
                    if controller then
                        -- 強制彈出/取消當前的 Attack Task
                        pcall(function() controller:popTask() end)
                        
                        -- 1. 獲取高度與速度
                        local current_alt = 6000
                        local current_speed = 250
                        local u1 = grp:getUnit(1)
                        if u1 and u1:isExist() then
                            local p = u1:getPoint()
                            local v = u1:getVelocity()
                            if p and p.y then current_alt = p.y end
                            if v then current_speed = math.max(150, math.floor(math.sqrt((v.x or 0)*(v.x or 0) + (v.z or 0)*(v.z or 0)))) end
                        end
                        
                        -- 2. 直接呼叫 controller:setTask() 重新設置航線點 (最乾淨、最可靠且能完全中斷舊任務)
                        local cur_x, cur_z = cmd.x, cmd.z
                        if u1 and u1:isExist() then
                            local pt = u1:getPoint()
                            if pt then cur_x, cur_z = pt.x, pt.z end
                        end
                        
                        local mission_task = {
                            id = 'Mission',
                            params = {
                                route = {
                                    points = {
                                        [1] = { x = cur_x, y = cur_z, alt = current_alt, speed = current_speed, action = 'Turning Point', type = 'Turning Point' },
                                        [2] = { x = cmd.x, y = cmd.z, alt = current_alt, speed = current_speed, action = 'Turning Point', type = 'Turning Point' }
                                    }
                                }
                            }
                        }
                        pcall(function() controller:setTask(mission_task) end)
                        
                        if env and env.info then
                            env.info(string.format("[GCI Command] Group %s vectored to X:%.1f, Z:%.1f", cmd.group_name, cmd.x, cmd.z))
                        end
                    end
                end
            elseif cmd.action == "attack_target" and cmd.group_name and cmd.target_name then
                local grp = Group.getByName(cmd.group_name) or (Unit.getByName(cmd.group_name) and Unit.getByName(cmd.group_name):getGroup())
                local tgt_unit = Unit.getByName(cmd.target_name)
                local tgt_grp = Group.getByName(cmd.target_name) or (tgt_unit and tgt_unit:getGroup())
                
                if grp and grp:isExist() and (tgt_unit or tgt_grp) then
                    local controller = grp:getController()
                    if controller then
                        -- 1. 設定 ROE 為 OPEN_FIRE_WEAPON_FREE (1: 優先交戰指定目標)
                        pcall(function()
                            if AI and AI.Option and AI.Option.Air and AI.Option.Air.id and AI.Option.Air.val and AI.Option.Air.val.ROE then
                                controller:setOption(AI.Option.Air.id.ROE, AI.Option.Air.val.ROE.OPEN_FIRE_WEAPON_FREE)
                            end
                        end)

                        -- 2. 嚴格符合 Hoggit DCS API 規範: pushTask AttackUnit / AttackGroup 包含 groupAttack與expend
                        if tgt_unit and tgt_unit:isExist() then
                            controller:pushTask({
                                id = 'AttackUnit',
                                params = {
                                    unitId = tgt_unit:getID(),
                                    groupAttack = true,
                                    expend = "All"
                                }
                            })
                        elseif tgt_grp and tgt_grp:isExist() then
                            controller:pushTask({
                                id = 'AttackGroup',
                                params = {
                                    groupId = tgt_grp:getID(),
                                    groupAttack = true,
                                    expend = "All"
                                }
                            })
                        end

                        if env and env.info then
                            env.info(string.format("[GCI Command] Group %s ordered to attack target %s (groupAttack=true, expend=All)", cmd.group_name, cmd.target_name))
                        end
                    end
                end
            elseif cmd.action == "set_roe" and cmd.group_name and cmd.roe_mode then
                local grp = Group.getByName(cmd.group_name) or (Unit.getByName(cmd.group_name) and Unit.getByName(cmd.group_name):getGroup())
                if grp and grp:isExist() then
                    local controller = grp:getController()
                    if controller and AI and AI.Option and AI.Option.Air and AI.Option.Air.id then
                        pcall(function()
                            local roe_map = {
                                WEAPON_FREE = AI.Option.Air.val.ROE.WEAPON_FREE,           -- 0
                                WEAPON_HOLD = AI.Option.Air.val.ROE.WEAPON_HOLD,           -- 4
                                RETURN_FIRE = AI.Option.Air.val.ROE.RETURN_FIRE,           -- 3
                                DESIGNATED_TARGET = AI.Option.Air.val.ROE.OPEN_FIRE       -- 2 (DCS 官方 API: OPEN_FIRE 表示只攻擊指定目標)
                            }
                            local roe_val = roe_map[cmd.roe_mode] or AI.Option.Air.val.ROE.OPEN_FIRE
                            controller:setOption(AI.Option.Air.id.ROE, roe_val)
                            
                            -- 如果將 ROE 設為 WEAPON_HOLD 或 RETURN_FIRE，強制清空/彈出當前主動攻擊 Task
                            if cmd.roe_mode == "WEAPON_HOLD" or cmd.roe_mode == "RETURN_FIRE" then
                                controller:popTask()
                            end
                        end)
                    end
                end
            end
        end)
        
        if not status_run and env and env.info then
            env.info("[External_GCI_Exporter] Command Process Error: " .. tostring(err))
        end
    end
end

local function export_telemetry_safe(time, args)
    process_incoming_commands()
    local status, err = pcall(function()
        local airbases = get_airbases()
        local blue_side = 2
        local red_side = 1
        if coalition and type(coalition.side) == "table" then
            if coalition.side.BLUE then blue_side = coalition.side.BLUE end
            if coalition.side.RED then red_side = coalition.side.RED end
        end
        local blue_telemetry = get_telemetry_for_coalition(blue_side, red_side)
        local red_telemetry = get_telemetry_for_coalition(red_side, blue_side)
        
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
            friendlies = red_telemetry.friendlies,
            hostiles = red_telemetry.hostiles,
            airbases = airbases
        })
        udp:sendto(packet_red, UDP_IP, UDP_PORT)
    end)
    
    if not status then
        if env and env.info then
            env.info("[External_GCI_Exporter] EXPORT ERROR: " .. tostring(err))
        end
    end
    
    -- 確保當 timer 傳入的 time 為 nil 時（如手動/特殊呼叫），使用 timer.getTime() 作為基準時間
    local current_time = time or (timer and timer.getTime and timer.getTime()) or 0
    return current_time + UPDATE_INTERVAL
end

timer.scheduleFunction(export_telemetry_safe, nil, timer.getTime() + UPDATE_INTERVAL)
env.info("Pure DCS API External GCI Exporter Started!")
