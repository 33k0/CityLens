# -*- coding: utf-8 -*-
"""Text pools for the generated constituent emails. Every sentence is fictional.

Each topic: cat, sub, act (actionable), subj (subjects per lang), issue / detail / ask pools per lang.
ask entries are (stance, text). Issue/detail sentences never name a place (location comes from LOC sentences).
"""

LOC_INT = {
    "en": ["I live near {A} and {B}.", "We live near the corner of {A} and {B}.", "I live by {A} and {B} with my family.",
           "I've been a homeowner near {A} and {B} for {Y} years.", "I rent an apartment near {A} and {B}.",
           "My house is right at {A} and {B}.", "We live just off {A} near {B}.", "I live at the corner of {A} and {B}."],
    "es": ["Vivo cerca de {A} y {B}.", "Nosotros vivimos cerca de {A} y {B} desde hace {Y} años."],
    "vi": ["Tôi sống gần {A} và {B}.", "Gia đình tôi ở gần {A} và {B}."],
}
LOC_INT_OWNER = ["I own a small business near {A} and {B}.", "I run a shop near the corner of {A} and {B}."]
LOC_NB = {
    "en": ["I live in {N}.", "We've lived in {N} for {Y} years.", "I'm a {N} homeowner.", "Our family has been in {N} for {Y} years.",
           "I've lived in {N} since {YR}.", "My family and I live in {N}."],
    "es": ["Vivo en {N}.", "Vivimos en {N} desde hace {Y} años."],
    "vi": ["Tôi sống ở khu {N}.", "Gia đình tôi sống ở khu {N} đã {Y} năm."],
}
SIG_NB = {"en": "{N} resident", "es": "Residente de {N}", "vi": "Cư dân khu {N}"}

GREET = {
    "en": ["Dear Councilmember,", "Hello,", "To the City Council,", "Dear Council Office,", "Hi,", "Dear Mayor and Council,", ""],
    "es": ["Estimados concejales,", "Buenas tardes,", "Hola,", "Estimado Concejo Municipal,"],
    "vi": ["Kính gửi Hội đồng,", "Kính gửi quý vị,", "Xin chào,"],
}
SIGNOFF = {
    "en": ["Thank you,", "Thanks,", "Sincerely,", "Regards,", "Best,", "Respectfully,", ""],
    "es": ["Gracias,", "Atentamente,", "Saludos,"],
    "vi": ["Trân trọng,", "Cảm ơn quý vị,"],
}

T = {}

T["streetlight"] = dict(cat="infrastructure_streets", sub="streetlight_outage", act=True, owner_ok=True,
    subj={"en": ["Streetlights out on our block", "Dark street again", "streetlight outage, third report", "Please fix our streetlights",
                 "Street lights have been out for weeks", "Lights out near my home"],
          "es": ["Las luces de la calle no funcionan", "Calle oscura otra vez"],
          "vi": ["Đèn đường bị tắt", "Đèn đường hỏng nhiều tuần"]},
    issue={"en": ["Three streetlights on our block have been out for almost a month.",
                  "The streetlights on our street go dark every few nights and then stay out for weeks.",
                  "Two streetlights near the bus stop have been out since the last storm.",
                  "Half the streetlights along our walk to school are out, and the copper wiring was stolen again.",
                  "The streetlight in front of our house has been flickering and then off entirely for six weeks.",
                  "Our whole block lost its streetlights after the wire theft in the spring and only one came back."],
           "es": ["Las luces de la calle llevan semanas apagadas en nuestra cuadra.",
                  "Varias luces de la calle están apagadas desde hace un mes."],
           "vi": ["Đèn đường ở khu nhà tôi đã tắt nhiều tuần nay.", "Mấy cột đèn đường gần trạm xe buýt bị tắt từ tháng trước."]},
    detail={"en": ["I reported it through the app twice and got an automatic reply both times.",
                   "My kids walk home from practice in the dark and I don't like it.",
                   "Cars have been broken into twice since the lights went out.",
                   "Seniors on our street have stopped taking evening walks.",
                   "The service request says closed, but nothing was fixed.",
                   "It's the darkest stretch in the neighborhood now."],
            "es": ["Mis hijos caminan de noche y da miedo.", "Lo reporté por la aplicación y nadie vino."],
            "vi": ["Buổi tối rất tối và nguy hiểm.", "Tôi đã báo qua ứng dụng nhưng chưa ai sửa."]},
    ask={"en": [("support", "I SUPPORT funding a faster repair crew and theft-proof wiring."),
                ("support", "Please send a crew to repair these lights."),
                ("support", "Please prioritize the streetlight maintenance contract and fix our block."),
                ("oppose", "I OPPOSE renewing a contract that leaves lights out this long.")],
         "es": [("support", "Apoyo que la ciudad arregle las luces pronto."), ("support", "Por favor manden a alguien a repararlas.")],
         "vi": [("support", "Tôi ủng hộ thành phố sửa đèn đường gấp."), ("support", "Xin quý vị cho người đến sửa sớm.")]})

T["pothole"] = dict(cat="infrastructure_streets", sub="pothole_pavement_repair", act=True, owner_ok=True,
    subj={"en": ["Pothole that keeps coming back", "Road surface is falling apart", "pothole damage to my car", "Please repave our street",
                 "Dangerous pothole", "Our street needs real repaving"],
          "es": ["Bache peligroso", "El bache sigue ahí"], "vi": ["Ổ gà nguy hiểm trên đường"]},
    issue={"en": ["There is a pothole on our street the size of a manhole cover and it has been there since winter.",
                  "The pothole patch from last year already crumbled and the hole is back, deeper.",
                  "The pavement on our street is cracked end to end and water sits in the low spots.",
                  "A pothole near the crosswalk bent the rim on my car last week.",
                  "Crews patched one pothole on our street and left four others right next to it.",
                  "The road surface on our block is so broken that delivery trucks swerve into the bike lane."],
           "es": ["Hay un bache enorme en nuestra calle desde hace meses.", "El bache de nuestra calle dañó la llanta de mi carro."],
           "vi": ["Có một ổ gà rất lớn trên đường nhà tôi từ mấy tháng nay."]},
    detail={"en": ["I've reported it three times and the ticket keeps closing.", "Cyclists have to swerve into traffic to avoid it.",
                   "My neighbor's tire blew out on it in March.", "A patch is not a fix if it fails in six months.",
                   "We pay our share of taxes and the street looks abandoned."],
            "es": ["Es peligroso para las bicicletas.", "Lo reporté varias veces."],
            "vi": ["Xe máy và xe đạp rất dễ bị ngã.", "Tôi đã báo nhiều lần."]},
    ask={"en": [("support", "Please repave the block instead of patching it again."), ("support", "I SUPPORT more road-repair funding for residential streets."),
                ("support", "Please fix this pothole before someone gets hurt."), ("oppose", "I OPPOSE spending on cosmetic projects while basic streets crumble.")],
         "es": [("support", "Por favor arréglenlo ya."), ("oppose", "Me opongo a que lo dejen así tanto tiempo.")],
         "vi": [("support", "Xin thành phố cho sửa đường sớm.")]})

T["drainage"] = dict(cat="infrastructure_streets", sub="drainage_flooding", act=True, owner_ok=False,
    subj={"en": ["Storm drain backs up every rain", "Flooding at our curb", "Drain clogged again"], "es": ["Se inunda la calle"], "vi": ["Cống bị nghẹt"]},
    issue={"en": ["Every time it rains the storm drain at our curb backs up and water reaches the garages.",
                  "The storm drain on our block has been clogged with leaves and silt since October.",
                  "Water pools across the whole intersection after any storm because the drain is blocked."],
           "es": ["Cada vez que llueve la calle se inunda porque el drenaje está tapado."],
           "vi": ["Mỗi lần mưa nước ngập vào sân vì cống bị nghẹt."]},
    detail={"en": ["Last winter it got into two of our neighbors' garages.", "Kids walking to school have to wade through it."],
            "es": ["El agua llegó a la cochera del vecino."], "vi": ["Nước tràn vào nhà hàng xóm."]},
    ask={"en": [("support", "Please have Public Works clear the drain before the rainy season."),
                ("support", "I SUPPORT funding storm drain upgrades on residential streets.")],
         "es": [("support", "Por favor limpien el drenaje antes de las lluvias.")], "vi": [("support", "Xin cho người đến thông cống trước mùa mưa.")]})

T["crosswalk"] = dict(cat="infrastructure_streets", sub="infrastructure_equity", act=True, owner_ok=True,
    subj={"en": ["Unsafe crossing near the school", "We need a crosswalk", "Speeding on our street"], "es": ["Cruce peligroso"], "vi": ["Đường băng qua nguy hiểm"]},
    issue={"en": ["The crossing by the elementary school has no signal and drivers do fifty through it.",
                  "Cars speed down our street every morning and there is no marked crosswalk for the kids.",
                  "Other neighborhoods got flashing beacons at their school crossings years ago and we are still waiting."],
           "es": ["No hay paso de peatones cerca de la escuela y los carros pasan muy rápido."],
           "vi": ["Gần trường học không có vạch qua đường và xe chạy rất nhanh."]},
    detail={"en": ["A crossing guard was nearly hit in September.", "We asked for a traffic study two years ago."],
            "es": ["Casi atropellan a un niño el mes pasado."], "vi": ["Tháng trước suýt có tai nạn."]},
    ask={"en": [("support", "Please install a flashing beacon and a marked crosswalk this year."),
                ("support", "I SUPPORT equal traffic-safety funding for every neighborhood, not just the loudest ones.")],
         "es": [("support", "Pedimos que pongan un cruce con luces.")], "vi": [("support", "Xin thành phố làm vạch qua đường và đèn báo.")]})

T["dumping"] = dict(cat="sanitation_environment_quality", sub="illegal_dumping_creek", act=True, owner_ok=True,
    subj={"en": ["Illegal dumping again", "Mattresses and trash dumped on our street", "dumping problem", "Couch dumped on the sidewalk for two weeks"],
          "es": ["Basura tirada en la calle", "Tiran basura otra vez"], "vi": ["Rác bị vứt bừa bãi"]},
    issue={"en": ["Someone keeps dumping mattresses and construction debris at the end of our street.",
                  "There is a pile of dumped furniture and trash bags on the sidewalk that has been there two weeks.",
                  "People dump old tires and paint cans by the creek path behind our homes.",
                  "The vacant lot next to us has become a dump site for appliances and bags of trash."],
           "es": ["Siguen tirando basura y muebles viejos en la esquina de nuestra cuadra.", "Hay colchones y basura tirados junto al arroyo."],
           "vi": ["Có người vứt nệm cũ và rác ở góc đường nhà tôi.", "Rác và đồ cũ bị vứt bên lề đường cả tháng nay."]},
    detail={"en": ["It smells and the rats are getting into yards.", "We cleaned it up ourselves twice and it came right back.",
                   "Kids have to walk around it into the street.", "I reported it in the app and the pickup took eighteen days."],
            "es": ["Huele muy mal y hay ratas.", "Lo reportamos y tardaron semanas."], "vi": ["Rất hôi và có chuột.", "Tôi đã báo nhưng lâu lắm mới dọn."]},
    ask={"en": [("support", "Please clean it up and put a camera at this spot."), ("support", "I SUPPORT more dumping enforcement and faster cleanup."),
                ("support", "Please schedule a cleanup crew and post no-dumping signs.")],
         "es": [("support", "Apoyo que la ciudad limpie y ponga cámaras."), ("support", "Por favor vengan a limpiar pronto.")],
         "vi": [("support", "Xin thành phố dọn sạch và gắn camera."), ("support", "Tôi ủng hộ phạt nặng người vứt rác.")]})

T["freeway_air"] = dict(cat="sanitation_environment_quality", sub="freeway_air_quality", act=True, owner_ok=False,
    subj={"en": ["Freeway noise and air", "Sound wall request"], "es": ["Ruido y aire de la autopista"], "vi": ["Tiếng ồn xa lộ"]},
    issue={"en": ["We live close enough to the freeway that the windowsills are black with soot every week.",
                  "The freeway noise behind our homes is constant and my son's asthma has gotten worse."],
           "es": ["Vivimos junto a la autopista y el aire siempre está sucio."], "vi": ["Nhà tôi sát xa lộ, bụi và tiếng ồn suốt ngày."]},
    detail={"en": ["There is no sound wall on our side, only a chain-link fence."], "es": ["Mi hija tiene asma."], "vi": ["Con tôi bị suyễn."]},
    ask={"en": [("support", "Please fund a sound wall and tree planting along this stretch.")],
         "es": [("support", "Pedimos un muro de sonido y más árboles.")], "vi": [("support", "Xin xây tường cách âm và trồng cây.")]})

T["rent_support"] = dict(cat="housing_affordability_policy", sub="rent_stabilization", act=False, tenant=True,
    subj={"en": ["Support the rent cap amendment", "Please lower the rent cap", "Renter asking for a YES vote"],
          "es": ["Apoyo el límite de renta", "Por favor bajen el aumento de renta"], "vi": ["Ủng hộ giới hạn tăng tiền thuê"]},
    issue={"en": ["My rent went up again this year and it now takes more than half my paycheck.",
                  "Every lease renewal is another increase, and wages in my house have not moved.",
                  "Our building changed owners and the first letter we got was a rent increase.",
                  "I'm a renter and the annual increases are the reason my friends have left the city."],
           "es": ["Cada año la renta sube más de lo que ganamos.", "Somos inquilinos y la renta ya es más de la mitad de nuestro sueldo."],
           "vi": ["Mỗi năm tiền thuê nhà lại tăng mà lương không tăng.", "Gia đình tôi thuê nhà và tiền thuê tăng liên tục."]},
    detail={"en": ["We are not asking for a handout, just predictability.", "I work two jobs and I'm still behind.",
                   "My kids go to school here and I don't want to move them again."],
            "es": ["Tenemos miedo de perder la casa.", "Trabajo en dos lugares y no alcanza."],
            "vi": ["Chúng tôi rất lo sẽ phải dọn đi.", "Tôi làm hai việc mà vẫn không đủ."]},
    ask={"en": [("support", "I SUPPORT lowering the annual rent-increase cap. Please vote yes."),
                ("support", "Please vote YES on the rent cap amendment.")],
         "es": [("support", "Apoyo bajar el límite de aumento de renta. Por favor voten que sí.")],
         "vi": [("support", "Xin quý vị bỏ phiếu thuận để giảm mức trần tăng tiền thuê.")]})

T["rent_oppose"] = dict(cat="housing_affordability_policy", sub="rent_stabilization", act=False, owner_ok=False,
    subj={"en": ["Small landlord opposed to the rent cap change", "Please don't lower the cap"], "es": [], "vi": []},
    issue={"en": ["I own a fourplex and my insurance and property taxes went up far more than the proposed cap.",
                  "As a small landlord, a lower cap means I can't keep up with repairs on an older building.",
                  "We own one rental duplex and the cost of a new roof alone wiped out three years of increases."]},
    detail={"en": ["Big corporate owners can absorb this. Mom-and-pop owners can't.", "I keep my rents below market already."]},
    ask={"en": [("oppose", "I OPPOSE lowering the rent cap without a capital-improvement pass-through."),
                ("oppose", "Please vote no on the rent ordinance amendment.")]})

T["eviction"] = dict(cat="housing_affordability_policy", sub="tenant_protection_eviction", act=True, tenant=True,
    subj={"en": ["Renovation evictions in our building", "Tenant protections needed"], "es": ["Nos quieren desalojar"], "vi": ["Bị ép dọn nhà"]},
    issue={"en": ["Our landlord sent notices to six units saying we have to leave for renovations that never seem to happen.",
                  "Tenants in my building are being pushed out with 'substantial remodel' notices and the units get re-rented at double."],
           "es": ["El dueño nos dio aviso de desalojo para remodelar, pero nunca remodela."],
           "vi": ["Chủ nhà bắt chúng tôi dọn đi để sửa nhà nhưng thật ra là để tăng giá."]},
    detail={"en": ["Most of us have lived here more than ten years."], "es": ["Llevamos doce años aquí."], "vi": ["Chúng tôi đã ở đây hơn mười năm."]},
    ask={"en": [("support", "Please close the remodel loophole and require relocation payments.")],
         "es": [("support", "Pedimos que cierren ese hueco en la ley y protejan a los inquilinos.")],
         "vi": [("support", "Xin thành phố bảo vệ người thuê nhà và đóng lỗ hổng này.")]})

T["fourplex_support"] = dict(cat="housing_affordability_policy", sub="zoning_density_reform", act=False, owner_ok=False,
    subj={"en": ["Yes on fourplexes", "Support the fourplex zoning reform", "Let us build more homes"], "es": ["A favor de más vivienda"], "vi": []},
    issue={"en": ["My grown kids can't afford to live in the city they grew up in, and fourplexes are a reasonable fix.",
                  "Allowing fourplexes on single-family lots is a modest change that lets neighborhoods grow gently.",
                  "I'd like to build a small fourplex on my lot so my parents and my daughter can live nearby."],
           "es": ["Mis hijos adultos no pueden pagar renta aquí y necesitamos más unidades de vivienda."]},
    detail={"en": ["Every older neighborhood here already has duplexes and nobody notices them.", "We need housing near jobs and transit."],
            "es": ["Necesitamos más opciones."]},
    ask={"en": [("support", "I SUPPORT the fourplex reform. Please approve it."), ("support", "Please vote yes on the citywide fourplex zoning reform.")],
         "es": [("support", "Por favor voten a favor de la reforma.")]})

T["fourplex_oppose"] = dict(cat="housing_affordability_policy", sub="housing_supply_infrastructure", act=False, owner_ok=False,
    subj={"en": ["Concerns about fourplex upzoning", "Slow down the fourplex reform", "Oppose blanket upzoning"], "es": [], "vi": []},
    issue={"en": ["Our sewer lines and school classrooms are already at capacity, and fourplexes on every lot will make that worse.",
                  "Parking on our street is already full every night, and the fourplex reform has no plan for it.",
                  "Blanket upzoning of single-family neighborhoods ignores the water and sewer infrastructure underneath them."]},
    detail={"en": ["I'm not against housing, I'm against doing it without a plan.", "We bought here for the neighborhood as it is."]},
    ask={"en": [("oppose", "I OPPOSE the fourplex reform as written. Please phase it in with an infrastructure plan."),
                ("oppose", "Please vote no on citywide fourplexes.")]})

T["habitability"] = dict(cat="code_enforcement_habitability", sub="habitability_hot_water_mold", act=True, tenant=True,
    subj={"en": ["No heat and mold in our apartment", "Landlord won't fix anything", "Request for a rental inspection"],
          "es": ["Sin agua caliente", "Moho en el apartamento"], "vi": ["Không có nước nóng", "Nhà bị mốc"]},
    issue={"en": ["Our apartment has had black mold in the bathroom and bedroom since spring and the landlord just paints over it.",
                  "We have had no hot water for nine days and the property manager stopped answering.",
                  "The heater in our unit has been broken since November and the landlord says it's not urgent.",
                  "The building's front door lock has been broken for months and strangers sleep in the stairwell."],
           "es": ["Llevamos más de una semana sin agua caliente y el dueño no responde.", "Hay moho en las paredes del cuarto de mis hijos."],
           "vi": ["Căn hộ của chúng tôi không có nước nóng hơn một tuần.", "Phòng ngủ bị mốc mà chủ nhà không sửa."]},
    detail={"en": ["My daughter has asthma and it's getting worse.", "I called code enforcement and was told the wait is weeks.",
                   "Other tenants are afraid to complain."],
            "es": ["Mis hijos se bañan con agua fría.", "Tengo miedo de quejarme."], "vi": ["Con tôi bị ho suốt.", "Hàng xóm sợ không dám báo."]},
    ask={"en": [("support", "Please send an inspector and hold the landlord accountable."),
                ("support", "I SUPPORT proactive rental inspections so tenants don't have to fight alone.")],
         "es": [("support", "Por favor manden un inspector pronto.")], "vi": [("support", "Xin thành phố cử người kiểm tra và buộc chủ nhà sửa.")]})

T["blight"] = dict(cat="code_enforcement_habitability", sub="derelict_blight_enforcement", act=True, owner_ok=True,
    subj={"en": ["Abandoned house on our street", "Vacant building is a hazard", "Blighted property complaint"], "es": ["Casa abandonada"], "vi": []},
    issue={"en": ["The house two doors down has been vacant for three years, the roof is caving in, and people break in at night.",
                  "A boarded-up commercial building on our corner has trash piling up and the fence is falling onto the sidewalk.",
                  "The abandoned property next door has a pool full of green water and the weeds are taller than the fence."],
           "es": ["La casa abandonada de la esquina está llena de basura y entra gente de noche."]},
    detail={"en": ["Code enforcement opened a case and closed it without anything changing.", "We worry about a fire."],
            "es": ["Tenemos miedo de un incendio."]},
    ask={"en": [("support", "Please enforce the vacant building ordinance and fine the owner."),
                ("support", "Please send code enforcement back out and keep the case open until it's secured.")],
         "es": [("support", "Pedimos que la ciudad obligue al dueño a limpiar.")]})

T["permit_delay"] = dict(cat="code_enforcement_habitability", sub="permit_backlog_delays", act=True, owner_ok=True,
    subj={"en": ["ADU permit stuck for months", "Permit delays are killing my business", "Remodel permit backlog", "Solar permit still pending"],
          "es": ["Permisos tardan demasiado"], "vi": ["Giấy phép chờ quá lâu"]},
    issue={"en": ["Our ADU permit has been in plan review for eleven months and every round brings a new comment.",
                  "I signed a lease for my bakery last winter and still can't open because the permit is stuck.",
                  "A simple kitchen remodel permit has taken five months and three resubmittals.",
                  "My solar permit has been pending for twelve weeks for a standard rooftop system."],
           "es": ["Llevo meses esperando el permiso para una pequeña remodelación."],
           "vi": ["Tôi chờ giấy phép sửa nhà hơn năm tháng rồi."]},
    detail={"en": ["I'm paying rent and a loan on a space I can't use.", "Nobody at the permit center can tell me where it is in the queue.",
                   "The contractor is about to walk away."],
            "es": ["Cada vez piden otro documento."], "vi": ["Mỗi lần lại đòi thêm giấy tờ."]},
    ask={"en": [("support", "Please fix the permit backlog and set a real turnaround time."),
                ("support", "I SUPPORT the permitting modernization, but please add plan checkers, not just software.")],
         "es": [("support", "Por favor simplifiquen el proceso de permisos.")], "vi": [("support", "Xin thành phố giải quyết giấy phép nhanh hơn.")]})

T["permit_fees"] = dict(cat="code_enforcement_habitability", sub="permit_fees_staffing", act=True, owner_ok=True,
    subj={"en": ["Permit fee increase", "Oppose higher permit fees"], "es": [], "vi": []},
    issue={"en": ["The proposed permit fee schedule raises fees on small projects by almost forty percent with no promise of faster service.",
                  "Raising permit fees again while review times keep growing is backwards."]},
    detail={"en": ["Small contractors pass these costs straight to homeowners."]},
    ask={"en": [("oppose", "I OPPOSE the fee increase unless it pays for more plan check staff.")]})

T["safety_patrol"] = dict(cat="public_safety_emergency_response", sub="patrol_staffing_levels", act=True, owner_ok=True,
    subj={"en": ["Car break-ins on our street", "Catalytic converter thefts", "We need more patrols", "Slow police response"],
          "es": ["Robos en el vecindario"], "vi": ["Trộm cắp trong khu phố"]},
    issue={"en": ["There have been five car break-ins on our street since August and two catalytic converter thefts.",
                  "Someone tried to break into our garage at 3 a.m. and police took over an hour to come.",
                  "Package theft and car break-ins on our block have doubled this year.",
                  "My neighbor's catalytic converter was cut off in broad daylight last week."],
           "es": ["En mi cuadra ha habido varios robos a autos y casas.", "Nos robaron el convertidor catalítico del carro."],
           "vi": ["Khu phố tôi bị trộm xe và đập kính xe nhiều lần.", "Nhà hàng xóm bị trộm hai lần trong tháng."]},
    detail={"en": ["We put up cameras ourselves.", "Nobody even called back about the report.", "People are scared to park on the street."],
            "es": ["La policía tarda mucho en llegar."], "vi": ["Cảnh sát đến rất trễ."]},
    ask={"en": [("support", "I SUPPORT more patrols and community service officers in our area."),
                ("support", "Please fund faster police response for property crime.")],
         "es": [("support", "Pedimos más vigilancia y que respondan a tiempo.")], "vi": [("support", "Xin tăng cường tuần tra trong khu phố.")]})

T["safety_cameras"] = dict(cat="public_safety_emergency_response", sub="surveillance_privacy", act=False, owner_ok=False,
    subj={"en": ["Concerns about license plate cameras", "Surveillance cameras"], "es": [], "vi": []},
    issue={"en": ["The plan to add license-plate readers and surveillance cameras on every arterial goes too far for a city that values privacy.",
                  "I don't want my daily movements logged by surveillance cameras with no clear rule on who can see the data."]},
    detail={"en": ["There's no public data retention policy in the staff report."]},
    ask={"en": [("oppose", "I OPPOSE expanding surveillance cameras without a privacy ordinance first.")]})

T["safety_youth"] = dict(cat="public_safety_emergency_response", sub="crime_prevention_youth", act=True, owner_ok=False,
    subj={"en": ["Fund youth programs", "Keep the teen center open late"], "es": ["Programas para jóvenes"], "vi": []},
    issue={"en": ["The community center near us cut its teen hours and since then there are more kids with nothing to do at night.",
                  "Late-night youth programs and summer jobs prevent more crime than another patrol car ever will."],
           "es": ["El centro comunitario cerró los programas para jóvenes en la noche."]},
    detail={"en": ["My son found his first job through one of those programs."], "es": ["Los jóvenes no tienen a dónde ir."]},
    ask={"en": [("support", "Please restore funding for youth programs in the public safety budget.")],
         "es": [("support", "Apoyo que la ciudad pague más programas para jóvenes.")]})

T["datacenter"] = dict(cat="environment_development_review", sub="flood_water_risk", act=False, owner_ok=False,
    subj={"en": ["Terra Verde data center water use", "Oppose the data center"], "es": ["No al centro de datos"], "vi": ["Phản đối trung tâm dữ liệu"]},
    issue={"en": ["A data center that needs millions of gallons for cooling is the wrong project during a drought.",
                  "The Terra Verde data center EIR does not explain where the cooling water comes from in a dry year."],
           "es": ["Un centro de datos que usa tanta agua no tiene sentido cuando nos piden ahorrar."],
           "vi": ["Trung tâm dữ liệu dùng quá nhiều nước và điện."]},
    detail={"en": ["The north end already floods."], "es": ["Además hay ruido y camiones."], "vi": ["Khu vực đó hay bị ngập."]},
    ask={"en": [("oppose", "I OPPOSE certifying the EIR as written."), ("oppose", "Please vote no on the Terra Verde data center.")],
         "es": [("oppose", "Por favor voten que no.")], "vi": [("oppose", "Xin quý vị bỏ phiếu chống.")]})

T["datacenter_cond"] = dict(cat="environment_development_review", sub="conditional_approval", act=True, owner_ok=False,
    subj={"en": ["Data center: approve only with conditions"], "es": [], "vi": []},
    issue={"en": ["I can live with the Terra Verde data center if it runs on recycled water and caps generator testing."]},
    detail={"en": ["The tax base matters, but so does the neighborhood."]},
    ask={"en": [("support", "I SUPPORT approval only with a binding recycled-water condition and a community benefit agreement.")]})

T["blossom"] = dict(cat="environment_development_review", sub="traffic_neighborhood_character", act=False, owner_ok=False,
    subj={"en": ["Blossom Hill rezoning", "Oppose the Blossom Hill strip mall rezoning"], "es": [], "vi": []},
    issue={"en": ["Rezoning the Blossom Hill retail parcel for another strip mall will add traffic that is already jammed at school pickup.",
                  "The Blossom Hill parcel should be housing or a park, not more empty retail."]},
    detail={"en": ["Half the storefronts in the existing center are vacant."]},
    ask={"en": [("oppose", "I OPPOSE the rezoning as proposed."), ("oppose", "Please deny the Blossom Hill rezoning application.")]})

T["senior"] = dict(cat="other", sub="senior_services_general", act=True, owner_ok=False,
    subj={"en": ["Senior center hours", "Please keep the senior lunch program", "Library hours cut"], "es": ["Centro para personas mayores"],
          "vi": ["Giữ giờ mở cửa trung tâm người cao tuổi"]},
    issue={"en": ["The senior center near us cut its hours to three days a week and my father now eats lunch alone most days.",
                  "The senior lunch program is the only place many older neighbors see anyone all week.",
                  "Our branch library closed on Sundays and Mondays, and it was where seniors went to stay cool."],
           "es": ["El centro para personas mayores redujo sus horas y mi mamá ya no tiene a dónde ir."],
           "vi": ["Trung tâm người cao tuổi giảm giờ mở cửa, mẹ tôi không còn nơi gặp bạn bè."]},
    detail={"en": ["It costs very little compared to what it gives back."], "es": ["Ella se siente muy sola."], "vi": ["Bà rất buồn và cô đơn."]},
    ask={"en": [("support", "Please restore the full senior center schedule.")], "es": [("support", "Por favor regresen el horario completo.")],
         "vi": [("support", "Xin giữ nguyên giờ mở cửa như trước.")]})

T["cost"] = dict(cat="other", sub="general_cost_of_living", act=False, owner_ok=False,
    subj={"en": ["Everything costs too much", "Can't keep up", "Cost of living"], "es": ["Todo está muy caro"], "vi": ["Giá cả quá đắt"]},
    issue={"en": ["Between rent, groceries and gas, my family is falling further behind every month.",
                  "Everything in this city costs more every year and nobody in charge seems to notice.",
                  "I make a decent salary and still can't save anything after rent and childcare."],
           "es": ["La renta, la comida y la gasolina están carísimas y ya no alcanza.", "Todo sube y los sueldos no."],
           "vi": ["Tiền nhà, tiền chợ, tiền xăng đều tăng, gia đình tôi rất khó khăn."]},
    detail={"en": ["I don't know what the council can do, but please do something.", "We're thinking about leaving the Bay Area."],
            "es": ["No sé qué pueden hacer, pero por favor piensen en nosotros."], "vi": ["Xin quý vị nghĩ đến những gia đình như chúng tôi."]},
    ask={"en": [("unclear", "I just wanted someone to hear it.")], "es": [("unclear", "Solo quería que lo supieran.")],
         "vi": [("unclear", "Tôi chỉ muốn quý vị biết.")]})

T["boards"] = dict(cat="governance_civic_rights", sub="boards_commissions_fairness", act=True, owner_ok=False,
    subj={"en": ["Who gets appointed to commissions", "Commission appointments process"], "es": [], "vi": []},
    issue={"en": ["Almost every member of the planning commission lives in the same few neighborhoods, and it shows in their votes.",
                  "The commission application process is hard to find and the interviews happen at 2 p.m. on weekdays."]},
    detail={"en": ["Working parents can't take off for a daytime interview."]},
    ask={"en": [("support", "Please hold evening interviews and publish the applicant pool for every commission.")]})

T["immigrant"] = dict(cat="governance_civic_rights", sub="immigrant_protection_sanctuary", act=False, owner_ok=False,
    subj={"en": ["Support protections for immigrant residents"], "es": ["Apoyo la protección a inmigrantes"], "vi": []},
    issue={"en": ["My neighbors are afraid to report crimes or take their kids to the clinic because of immigration raids."],
           "es": ["Muchas familias tienen miedo de salir por las redadas de inmigración."]},
    detail={"en": ["Trust in the police depends on this."], "es": ["Los niños tienen miedo de ir a la escuela."]},
    ask={"en": [("support", "I SUPPORT the resolution protecting immigrant residents.")], "es": [("support", "Apoyo la resolución para proteger a las familias inmigrantes.")]})

# who writes what
OWNER_TOPICS = ["pothole", "streetlight", "drainage", "crosswalk", "dumping", "blight", "permit_delay", "permit_fees", "safety_patrol",
                "safety_cameras", "fourplex_oppose", "fourplex_support", "rent_oppose", "boards", "senior", "freeway_air", "datacenter_cond"]
OWNER_W = [9, 8, 4, 6, 4, 4, 7, 3, 8, 3, 6, 4, 2, 2, 2, 1, 1]
TENANT_TOPICS = ["rent_support", "habitability", "streetlight", "dumping", "pothole", "safety_patrol", "eviction", "cost", "crosswalk",
                 "safety_youth", "senior", "immigrant", "freeway_air", "drainage", "fourplex_support"]
TENANT_W = [8, 7, 6, 6, 4, 4, 3, 3, 2, 2, 2, 2, 1, 1, 2]
NONEN_TOPICS = {"es": ["rent_support", "habitability", "streetlight", "dumping", "pothole", "safety_patrol", "cost", "eviction", "senior",
                       "immigrant", "crosswalk", "safety_youth", "permit_delay", "datacenter", "fourplex_support", "drainage", "blight", "freeway_air"],
                "vi": ["rent_support", "habitability", "streetlight", "dumping", "pothole", "safety_patrol", "cost", "senior", "eviction",
                       "permit_delay", "crosswalk", "datacenter", "drainage", "freeway_air"]}

# personal lines (filled with random numbers/relations) so short messages are not near-identical
PERSONAL = {
    "en": ["I've been in this city {Y} years and I've never written before.", "My {rel} and I talk about this every week.",
           "This is my {n} email about it.", "I work nights, so I see this at {h} a.m. most days.", "I'm a {job} and a parent of {k}.",
           "We moved here in {YR} and we'd like to stay.", "My {rel} uses a wheelchair, so this matters a lot.",
           "I coach youth soccer and the families ask me about this.", "I'm retired and I walk the neighborhood every morning.",
           "I'm writing on my lunch break, so I'll keep it short."],
    "es": ["Llevo {Y} años en esta ciudad.", "Mi {rel_es} y yo trabajamos en la limpieza de oficinas.", "Es la {n_es} vez que escribo.",
           "Tengo {k} hijos en la escuela del barrio.", "Trabajo de noche y llego a casa a las {h}.", "Llegamos en {YR} y queremos quedarnos.",
           "Soy {job_es} y casi no tengo tiempo, pero esto es importante."],
    "vi": ["Tôi đã sống ở thành phố này {Y} năm.", "Gia đình tôi có {k} con nhỏ.", "Đây là lần thứ {n_vi} tôi viết thư.",
           "Tôi làm ca đêm và về nhà lúc {h} giờ sáng.", "Chúng tôi đến đây từ năm {YR}.", "Mẹ tôi đã {age} tuổi và đi lại khó khăn."],
}
