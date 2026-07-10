-- =========================================================
-- TOP GUN: MAVERICK - SAM TRAP MODULE (峽谷低空狂飆)
-- =========================================================

env.info("LOADING TOPGUN SAM MODULE")

-- 確定 Core 已經載入
if not TOPGUN_MISSION then
    env.error("TOPGUN SAM MODULE FAILED: Core module not loaded!")
    return
end

local CanyonZone = ZONE:FindByName(TOPGUN_MISSION.CANYON_ZONE_NAME)
if not CanyonZone then
    env.warning("Canyon_Zone not found in mission! SAM logic will apply to the whole map.")
end

local SamGroups = SET_GROUP:New():FilterPrefixes(TOPGUN_MISSION.SAM_GROUP_PREFIX):FilterStart()
local PlayersSet = SET_CLIENT:New():FilterCoalitions("blue"):FilterActive():FilterStart()

-- 預設關閉所有陷阱防空飛彈的雷達
SamGroups:ForEachGroup(function(SamGroup)
    SamGroup:SetAIOff()
end)

local IsSamActive = false

-- 定時檢查玩家高度
local function CheckHardDeck()
    local OverLimit = false
    
    PlayersSet:ForEachClient(function(Client)
        if not Client:IsAlive() then return end
        
        local PlayerCoord = Client:GetCoordinate()
        if PlayerCoord then
            -- 如果有設定峽谷區域，只有在峽谷內的飛機會觸發機制
            if CanyonZone and not CanyonZone:IsCoordinateInZone(PlayerCoord) then
                return
            end
            
            -- 計算離地高度 (AGL) 轉換為英呎
            local AltFeetAGL = PlayerCoord:GetAltitude() * 3.28084
            local GroundElevationFeet = PlayerCoord:GetLandHeight() * 3.28084
            local AGL = AltFeetAGL - GroundElevationFeet
            
            if AGL > TOPGUN_MISSION.HARD_DECK_FEET then
                OverLimit = true
                -- 廣播警告給該玩家
                local msg = string.format("ALTITUDE WARNING! You are at %d ft! Descend below %d ft immediately!", math.floor(AGL), TOPGUN_MISSION.HARD_DECK_FEET)
                MESSAGE:New(msg, 2, "GCI"):ToClient(Client)
            end
        end
    end)
    
    if OverLimit and not IsSamActive then
        IsSamActive = true
        MESSAGE:New("SAM RADARS ACTIVE! MISSILE LOCK!", 5, "THREAT WARNING"):ToAll()
        SamGroups:ForEachGroup(function(SamGroup)
            SamGroup:SetAIOn()
        end)
    elseif not OverLimit and IsSamActive then
        IsSamActive = false
        MESSAGE:New("SAM radars lost track. Stay low.", 5, "GCI"):ToAll()
        SamGroups:ForEachGroup(function(SamGroup)
            SamGroup:SetAIOff()
        end)
    end
end

-- 每秒檢查一次
SCHEDULER:New(nil, CheckHardDeck, {}, 1, 1)

env.info("TOPGUN SAM MODULE LOADED")
