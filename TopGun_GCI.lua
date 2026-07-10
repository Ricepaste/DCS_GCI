env.info("TopGun GCI Script Loading...")

-- =========================================================
-- USER CONFIGURATION
-- =========================================================
local GCI_CALLSIGN = "Overlord"        -- 戰管的呼號
local ALERT_DISTANCE_NM = 50           -- 開始主動通報的距離 (海浬)
local MERGE_DISTANCE_NM = 5            -- 進入狗戰距離，GCI 自動閉嘴 (海浬)
local REPORT_COOLDOWN = 15             -- 每次播報的冷卻時間 (秒)，自動高頻更新
local LOW_FUEL_THRESHOLD = 0.20        -- 建議 RTB 的最低油量比例 (20%)
local RADAR_PREFIX = "AWACS"           -- 負責提供情報的友軍雷達/預警機前綴

-- =========================================================
-- INTERNAL STATE
-- =========================================================
local CheckedInPlayers = {}
local LastReportTime = {}
local ClientMenus = {}
local PlayerRTBNotified = {}

-- Create MOOSE SETs to track units dynamically
local SetPlayers = SET_CLIENT:New():FilterCoalitions("blue"):FilterActive():FilterStart()
local SetEnemies = SET_GROUP:New():FilterCoalitions("red"):FilterCategoryAirplane():FilterActive():FilterStart()
local SetRadarNetwork = SET_GROUP:New():FilterPrefixes(RADAR_PREFIX):FilterCoalitions("blue"):FilterStart()

-- =========================================================
-- UTILITIES & ADVANCED GCI FUNCTIONS
-- =========================================================

-- 計算態勢角
local function GetAspectDegrees(TargetCoord, TargetHeading, PlayerCoord)
    local AngleToPlayer = TargetCoord:HeadingTo(PlayerCoord)
    local Aspect = math.abs(AngleToPlayer - TargetHeading)
    if Aspect > 180 then Aspect = 360 - Aspect end
    return Aspect
end

-- 計算絕對航向 (Track)
local function GetCardinalDirection(heading)
    if heading >= 315 or heading < 45 then return "North"
    elseif heading >= 45 and heading < 135 then return "East"
    elseif heading >= 135 and heading < 225 then return "South"
    else return "West" end
end

-- 取得雷達網視野內的目標
local function GetKnownTargets()
    local KnownTargets = {}
    SetRadarNetwork:ForEachGroupAlive(function(RadarGroup)
        local DCSGroup = RadarGroup:GetDCSObject()
        if DCSGroup then
            local controller = DCSGroup:getController()
            if controller then
                local targets = controller:getDetectedTargets()
                if targets then
                    for _, targetData in pairs(targets) do
                        if targetData.object and targetData.object.isExist and targetData.object:isExist() then
                            local unitGroup = targetData.object:getGroup()
                            if unitGroup then
                                KnownTargets[unitGroup:getName()] = true
                            end
                        end
                    end
                end
            end
        end
    end)
    return KnownTargets
end

-- =========================================================
-- NCTR (非合作目標辨識) 邏輯
-- =========================================================
local function GetEnemyTypeIfIdentified(EnemyGroup)
    local IsIdentified = false
    local EnemyCoord = EnemyGroup:GetCoordinate()
    local EnemyHeading = EnemyGroup:GetHeading()
    
    -- 只有 GCI/AWACS 雷達網可以進行 NCTR
    SetRadarNetwork:ForEachGroupAlive(function(RadarGroup)
        if IsIdentified then return end
        local RadarCoord = RadarGroup:GetCoordinate()
        local DistNM = RadarCoord:Get2DDistance(EnemyCoord) * 0.000539957
        
        -- NCTR 條件：距離雷達小於 60 海浬，且敵機對著雷達站 HOT 或 COLD
        if DistNM < 60 then
            local AspectToRadar = GetAspectDegrees(EnemyCoord, EnemyHeading, RadarCoord)
            if AspectToRadar <= 45 or AspectToRadar >= 135 then
                IsIdentified = true
            end
        end
    end)
    
    if IsIdentified then
        local FirstUnit = EnemyGroup:GetUnit(1)
        if FirstUnit then
            return FirstUnit:GetTypeName()
        end
    end
    return nil
end

-- [F10 選單] Bogey Dope：主動請求最近目標
local function BogeyDope(Client)
    local ClientName = Client:GetPlayerName() or Client:GetCallsign() or Client:GetName()
    local PlayerCoord = Client:GetCoordinate()
    local KnownTargets = GetKnownTargets()
    
    local ClosestDist = 999999
    local ClosestEnemy = nil
    local ThreatAlt = 0
    local ThreatBearing = 0
    local ThreatAspect = 0
    
    SetEnemies:ForEachGroupAlive(function(EnemyGroup)
        if not KnownTargets[EnemyGroup:GetName()] then return end
        local EnemyCoord = EnemyGroup:GetCoordinate()
        local DistNM = PlayerCoord:Get2DDistance(EnemyCoord) * 0.000539957
        
        if DistNM < ClosestDist then
            ClosestDist = DistNM
            ClosestEnemy = EnemyGroup
            ThreatAlt = EnemyCoord:GetY() * 3.28084
            ThreatBearing = PlayerCoord:HeadingTo(EnemyCoord)
            ThreatAspect = GetAspectDegrees(EnemyCoord, EnemyGroup:GetHeading(), PlayerCoord)
        end
    end)
    
    if ClosestEnemy then
        local AspectText = "flanking"
        if ThreatAspect <= 45 then AspectText = "hot"
        elseif ThreatAspect >= 135 then AspectText = "cold" end
        
        local AltStr = ""
        if ThreatAlt < 1000 then AltStr = "on the deck"
        else AltStr = string.format("%d thousand", math.floor(ThreatAlt / 1000)) end
        
        local EnemyType = GetEnemyTypeIfIdentified(ClosestEnemy)
        local TypeStr = EnemyType and (", " .. EnemyType) or ""
        
        local Msg = string.format("%s, %s, BRAA %03d, %d, %s, %s, hostile%s.", 
            ClientName, GCI_CALLSIGN, math.floor(ThreatBearing), math.floor(ClosestDist), AltStr, AspectText, TypeStr)
        MESSAGE:New(Msg, 15, GCI_CALLSIGN):ToClient(Client)
        LastReportTime[ClientName] = timer.getTime() -- 重置冷卻
    else
        MESSAGE:New(ClientName .. ", " .. GCI_CALLSIGN .. ", radar is clean. No bogeys detected.", 10, GCI_CALLSIGN):ToClient(Client)
    end
end

-- [F10 選單] Request Picture：主動請求戰場圖像 (Multi-BRAA 展開)
local function RequestPicture(Client)
    local ClientName = Client:GetPlayerName() or Client:GetCallsign() or Client:GetName()
    local PlayerCoord = Client:GetCoordinate()
    local KnownTargets = GetKnownTargets()
    local GroupsList = {}
    
    -- 收集所有雷達看得到的敵軍群組
    SetEnemies:ForEachGroupAlive(function(EnemyGroup)
        if KnownTargets[EnemyGroup:GetName()] then
            local EnemyCoord = EnemyGroup:GetCoordinate()
            local DistNM = PlayerCoord:Get2DDistance(EnemyCoord) * 0.000539957
            local ThreatAlt = EnemyCoord:GetY() * 3.28084
            local ThreatBearing = PlayerCoord:HeadingTo(EnemyCoord)
            local EnemyHeading = EnemyGroup:GetHeading()
            local ThreatAspect = GetAspectDegrees(EnemyCoord, EnemyHeading, PlayerCoord)
            
            table.insert(GroupsList, {
                group = EnemyGroup,
                dist = DistNM,
                alt = ThreatAlt,
                bearing = ThreatBearing,
                aspect = ThreatAspect,
                heading = EnemyHeading
            })
        end
    end)
    
    if #GroupsList == 0 then
        MESSAGE:New(ClientName .. ", " .. GCI_CALLSIGN .. ", picture is clean.", 10, GCI_CALLSIGN):ToClient(Client)
    else
        -- 依照距離由近到遠排序
        table.sort(GroupsList, function(a, b) return a.dist < b.dist end)
        
        -- 組合廣播訊息
        local Msg = string.format("%s, %s, picture is %d groups (closest first).\n", ClientName, GCI_CALLSIGN, #GroupsList)
        
        -- 最多報出前 3 組，避免無線電洗頻
        local MaxReports = math.min(#GroupsList, 3)
        for i = 1, MaxReports do
            local gData = GroupsList[i]
            local AspectText = "flanking"
            if gData.aspect <= 45 then AspectText = "hot"
            elseif gData.aspect >= 135 then AspectText = "cold" end
            
            -- 高度簡化為 K (千英呎) 或是 Deck
            local AltStr = ""
            if gData.alt < 1000 then AltStr = "Deck"
            else AltStr = string.format("%dK", math.floor(gData.alt / 1000)) end
            
            local GroupNameStr = "Group " .. i
            
            local TrackText = GetCardinalDirection(math.deg(gData.heading))
            local EnemyType = GetEnemyTypeIfIdentified(gData.group)
            local TypeStr = EnemyType and (" / " .. EnemyType) or ""
            
            -- DCS 介面是非等寬字體，放棄空白對齊，改用緊湊的斜線 (/) 格式
            local BraaStr = string.format("%s: BRG %03d / RNG %02d NM / ALT %s / TRK %s / %s / hostile%s", 
                GroupNameStr, math.floor(gData.bearing), math.floor(gData.dist), AltStr, TrackText, AspectText, TypeStr)
                
            Msg = Msg .. BraaStr .. "\n"
        end
        
        -- 顯示較長時間 (20秒) 讓玩家有時間閱讀
        MESSAGE:New(Msg, 20, GCI_CALLSIGN):ToClient(Client)
    end
end

local CheckIn -- 前置宣告，解決互相呼叫的 nil 問題

-- 新增選單的函數
local function AddF10Menu(Client)
    if Client and Client:IsAlive() then
        SCHEDULER:New(nil, function()
            if Client:IsAlive() then
                local ClientGroup = Client:GetGroup()
                if ClientGroup then
                    local groupName = ClientGroup:GetName()
                    if ClientMenus[groupName] then
                        ClientMenus[groupName]:Remove()
                    end
                    
                    local ClientName = Client:GetPlayerName() or Client:GetCallsign() or Client:GetName()
                    local ClientMenu = MENU_GROUP:New(ClientGroup, "GCI Communications")
                    
                    -- 根據玩家的報到狀態，給予不同的子選單
                    if CheckedInPlayers[ClientName] then
                        MENU_GROUP_COMMAND:New(ClientGroup, "Bogey Dope (Closest Threat)", ClientMenu, BogeyDope, Client)
                        MENU_GROUP_COMMAND:New(ClientGroup, "Request Picture", ClientMenu, RequestPicture, Client)
                    else
                        MENU_GROUP_COMMAND:New(ClientGroup, "Check In", ClientMenu, CheckIn, Client)
                    end
                    
                    ClientMenus[groupName] = ClientMenu
                end
            end
        end, {}, 2.5)
    end
end

-- =========================================================
-- 1. F10 RADIO CHECK-IN SYSTEM
-- =========================================================
CheckIn = function(Client)
    local ClientName = Client:GetPlayerName() or Client:GetCallsign() or Client:GetName()
    CheckedInPlayers[ClientName] = true
    LastReportTime[ClientName] = 0 
    
    MESSAGE:New(GCI_CALLSIGN .. ", " .. ClientName .. " checking in as fragged.", 10, ClientName):ToClient(Client)
    
    SCHEDULER:New(nil, function()
        MESSAGE:New(ClientName .. ", " .. GCI_CALLSIGN .. ". Radar contact, welcome to the show.", 10, GCI_CALLSIGN):ToClient(Client)
    end, {}, 3)
    
    -- 重新載入 F10 選單 (因為狀態已變成 CheckedInPlayers，會自動長出進階選單)
    AddF10Menu(Client)
end

SetPlayers:HandleEvent(EVENTS.Birth, function(EventData) AddF10Menu(EventData.IniClient) end)
SetPlayers:HandleEvent(EVENTS.PlayerEnterAircraft, function(EventData) AddF10Menu(EventData.IniClient) end)
SetPlayers:ForEachClient(function(Client) AddF10Menu(Client) end)

-- =========================================================
-- 2. THREAT ANALYSIS ENGINE (Auto-Reporting)
-- =========================================================
local function GetThreatScore(DistanceNM, Aspect, AltFeet)
    local Score = 0
    if DistanceNM <= MERGE_DISTANCE_NM then return 0 end
    if DistanceNM <= ALERT_DISTANCE_NM then Score = Score + (ALERT_DISTANCE_NM - DistanceNM) * 2 end
    if Aspect <= 45 then Score = Score + 50
    elseif Aspect <= 135 then Score = Score + 20
    else Score = Score - 20 end
    Score = Score + (AltFeet / 1000)
    return Score
end

local function GCILoop()
    local KnownTargets = GetKnownTargets()

    SetPlayers:ForEachClient(function(Client)
        if not Client:IsAlive() then return end
        local ClientName = Client:GetPlayerName() or Client:GetCallsign() or Client:GetName()
        if not CheckedInPlayers[ClientName] then return end 
        
        local TimeNow = timer.getTime()
        if LastReportTime[ClientName] and (TimeNow - LastReportTime[ClientName] < REPORT_COOLDOWN) then return end
        
        local IsBingo, IsWinchester = false, false
        local fuelFrac = Client:GetFuel()
        if fuelFrac and fuelFrac < LOW_FUEL_THRESHOLD then IsBingo = true end
        IsWinchester = true
        local ammoTable = Client:GetAmmo()
        if ammoTable then
            for _, ammo in pairs(ammoTable) do
                -- 檢查數量 > 0
                if ammo.count and ammo.count > 0 then
                    -- 必須要有分類，且分類必須是 1(飛彈), 2(火箭彈), 3(炸彈)
                    -- 這會自動排除 0(機砲)、無分類的熱焰彈與外掛油箱
                    if ammo.desc and ammo.desc.category then
                        if ammo.desc.category == 1 or ammo.desc.category == 2 or ammo.desc.category == 3 then
                            IsWinchester = false
                            break
                        end
                    end
                end
            end
        end
        
        if IsBingo or IsWinchester then
            -- 只在第一次達到 Bingo 或 Winchester 時提醒，避免每 15 秒疲勞轟炸
            if not PlayerRTBNotified[ClientName] then
                local reason = "winchester"
                if IsBingo and IsWinchester then reason = "bingo fuel and winchester"
                elseif IsBingo then reason = "bingo fuel" end
                
                local Msg = string.format("%s, %s, you are %s. Recommend immediate RTB.", ClientName, GCI_CALLSIGN, reason)
                MESSAGE:New(Msg, 15, GCI_CALLSIGN):ToClient(Client)
                PlayerRTBNotified[ClientName] = true
            end
            -- 注意：這裡不加上 return，讓腳本繼續往下執行威脅掃描與 BRAA 播報
        else
            -- 如果玩家降落掛彈加油，解除提醒狀態
            PlayerRTBNotified[ClientName] = false
        end
        
        local PlayerCoord = Client:GetCoordinate()
        local HighestScore = 0
        local PrimaryThreat = nil
        local ThreatDist, ThreatAlt, ThreatBearing, ThreatAspect = 0, 0, 0, 0
        
        SetEnemies:ForEachGroupAlive(function(EnemyGroup)
            if not KnownTargets[EnemyGroup:GetName()] then return end
            
            local EnemyCoord = EnemyGroup:GetCoordinate()
            local DistNM = PlayerCoord:Get2DDistance(EnemyCoord) * 0.000539957
            
            if DistNM <= ALERT_DISTANCE_NM and DistNM > MERGE_DISTANCE_NM then
                local EnemyHeading = EnemyGroup:GetHeading()
                local Aspect = GetAspectDegrees(EnemyCoord, EnemyHeading, PlayerCoord)
                local AltFeet = EnemyCoord:GetY() * 3.28084
                local Score = GetThreatScore(DistNM, Aspect, AltFeet)
                
                if Score > HighestScore then
                    HighestScore = Score
                    PrimaryThreat = EnemyGroup
                    ThreatDist = DistNM
                    ThreatAlt = AltFeet
                    ThreatBearing = PlayerCoord:HeadingTo(EnemyCoord)
                    ThreatAspect = Aspect
                end
            end
        end)
        
        if PrimaryThreat and HighestScore > 0 then
            local AspectText = "flanking"
            if ThreatAspect <= 45 then AspectText = "hot"
            elseif ThreatAspect >= 135 then AspectText = "cold" end
            
            local AltStr = ""
            if ThreatAlt < 1000 then AltStr = "on the deck"
            else AltStr = string.format("%d thousand", math.floor(ThreatAlt / 1000)) end
            
            local EnemyType = GetEnemyTypeIfIdentified(PrimaryThreat)
            local TypeStr = EnemyType and (", " .. EnemyType) or ""
            
            local Msg = string.format("%s, %s, BRAA %03d, %d, %s, %s, hostile%s.", 
                ClientName, GCI_CALLSIGN, math.floor(ThreatBearing), math.floor(ThreatDist), AltStr, AspectText, TypeStr)
                
            MESSAGE:New(Msg, 15, GCI_CALLSIGN):ToClient(Client)
            LastReportTime[ClientName] = TimeNow
        end
    end)
end

SCHEDULER:New(nil, GCILoop, {}, 5, 5)
env.info("TopGun GCI Script Loaded Successfully.")
